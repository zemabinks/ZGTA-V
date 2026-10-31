use std::{collections::BTreeMap, env, fs, path::Path};
use naga::{back::msl, valid::{Capabilities, ValidationFlags, Validator}, ResourceBinding};
use serde_json::{json, Value};

// This tool consumes the owner's existing shader packs and the native reflection
// table. It never replaces the baseline metallib or invents resource slots.
fn stipple(text: &str) -> Result<String, String> {
    if text.contains("zgta_stipple_") { return Err("reserved stipple identifier collision".into()); }
    let start = text.find("fn main(").ok_or("fragment main missing")? + "fn main(".len();
    let mut depth = 1;
    let mut end = start;
    for (i, ch) in text[start..].char_indices() {
        if ch == '(' { depth += 1; }
        if ch == ')' { depth -= 1; if depth == 0 { end = start+i; break; } }
    }
    if depth != 0 { return Err("unbalanced main parameters".into()); }
    let params = &text[start..end];
    let (params, position) = if let Some(p) = params.find("@builtin(position)") {
        let tail = &params[p+"@builtin(position)".len()..];
        (params.to_owned(), tail.split(':').next().ok_or("position name missing")?.trim().to_owned())
    } else {
        (format!("{}{sep}@builtin(position) zgta_stipple_position : vec4<f32>",params,sep=if params.trim().is_empty(){""}else{", "}), "zgta_stipple_position".into())
    };
    let body = end + text[end..].find('{').ok_or("fragment body missing")?;
    let test = format!(r#"
 let zgta_stipple_code = zgta_stipple_threshold();
 if ((zgta_stipple_code & 16u) != 0u) {{
   let zgta_stipple_x = u32(max({position}.x, 0.0)) & 1u;
   let zgta_stipple_y = u32(max({position}.y, 0.0)) & 1u;
   let zgta_stipple_phase = zgta_stipple_x + 2u * zgta_stipple_y;
   if ((((zgta_stipple_code & 15u) >> zgta_stipple_phase) & 1u) == 0u) {{ discard; }}
 }} else {{
   let zgta_stipple_x = u32({position}.x) & 3u;
   let zgta_stipple_y = u32({position}.y) & 3u;
   let zgta_stipple_low = (((zgta_stipple_x ^ zgta_stipple_y) & 1u) << 1u) | (zgta_stipple_y & 1u);
   let zgta_stipple_high = ((((zgta_stipple_x ^ zgta_stipple_y) >> 1u) & 1u) << 1u) | (zgta_stipple_y >> 1u);
   if ((4u * zgta_stipple_low + zgta_stipple_high) >= zgta_stipple_code) {{ discard; }}
 }}
"#);
    let diagnostic = if text.contains("derivative_uniformity") { "" } else { "diagnostic(off, derivative_uniformity);\n" };
    Ok(format!("{diagnostic}{}{}{}{}{}\nfn zgta_stipple_threshold() -> u32 {{ return 7u; }}\n", &text[..start],params,&text[end..=body],test,&text[body+1..]))
}

fn translate(text: &str, reflection: &Value) -> Result<String, String> {
    let text = stipple(text)?;
    let module = naga::front::wgsl::parse_str(&text).map_err(|e| e.emit_to_string(&text))?;
    let info = Validator::new(ValidationFlags::all(), Capabilities::all()).validate(&module).map_err(|e| format!("{e:?}"))?;
    let mut resources = msl::EntryPointResources::default();
    for r in reflection["res"].as_array().ok_or("reflection resources missing")? {
        let binding = r[1].as_u64().ok_or("invalid binding")? as u32;
        let slot = u8::try_from(r[2].as_u64().ok_or("invalid slot")?).map_err(|_| "slot overflow")?;
        let kind = r[0].as_str().ok_or("resource kind missing")?;
        let mut target = msl::BindTarget::default();
        match kind {
            "ubo" | "ro" | "rw" => {target.buffer=Some(slot); target.mutable=kind=="rw";},
            "smp" => target.sampler=Some(msl::BindSamplerTarget::Resource(slot)),
            "tex" | "texms" | "depth" | "depthms" | "stw" | "str" | "strw" => target.texture=Some(slot),
            _ => return Err(format!("unsupported reflected kind {kind}")),
        }
        let globals:Vec<_> = module.global_variables.iter().filter_map(|(_,v)|v.binding.as_ref()).filter(|b|b.binding==binding).collect();
        if globals.len()!=1{return Err(format!("reflected binding {binding} does not identify one global"));}
        resources.resources.insert(ResourceBinding{group:globals[0].group,binding}, target);
    }
    resources.sizes_buffer = Some(15);
    let mut options = msl::Options::default();
    options.lang_version=(2,4);
    options.spirv_cross_compatibility=true;
    options.fake_missing_bindings=false;
    options.per_entry_point_map.insert("main".into(),resources);
    let (mut source, translated) = msl::write_string(&module,&info,&options,&msl::PipelineOptions::default()).map_err(|e| format!("{e:?}"))?;
    let entry=translated.entry_point_names.first().ok_or("no translated entry")?.as_ref().map_err(|e| format!("{e:?}"))?;
    let begin=source.find("uint zgta_stipple_threshold(").ok_or("threshold helper missing from MSL")?;
    let body=begin+source[begin..].find('{').ok_or("threshold helper body missing")?;
    let end=body+source[body..].find('}').ok_or("threshold helper body unbalanced")?;
    if source[body+1..end].trim()!="return 7u;" { return Err(format!("unexpected threshold helper: {}",&source[body+1..end])); }
    source.replace_range(body+1..end,"\n    return zgta_stipple_level;\n");
    source=format!("constant unsigned int zgta_stipple_level [[function_constant(0)]];\n{source}");
    // Naga sizes globals by declaration order; the baseline's immediate ABI
    // reserves 16 bytes then indexes lengths by the reflection alen table.
    if let Some(begin)=source.find("struct _mslBufferSizes {") {
        let end=begin+source[begin..].find("};").ok_or("sizes struct unterminated")?+2;
        let original=&source[begin..end];
        let fields:Vec<&str>=original.lines().filter_map(|l| l.trim().strip_prefix("uint ").and_then(|s|s.strip_suffix(';'))).collect();
        let globals:Vec<_>=module.global_variables.iter().filter(|(_,v)|module.types[v.ty].inner.needs_host_buffer_byte_size(&module.types)).collect();
        if fields.len()!=globals.len() {return Err("runtime-array field/global count mismatch".into());}
        let mut ordered=BTreeMap::new();
        for (name,(_,global)) in fields.iter().zip(globals) {
            let binding=global.binding.as_ref().ok_or("runtime-array binding absent")?.binding;
            let resource=reflection["res"].as_array().unwrap().iter().find(|r|r[1].as_u64()==Some(binding as u64)).ok_or("runtime-array reflection absent")?;
            let index=reflection["alen"].as_array().ok_or("length reflection missing")?.iter().find(|a|a[0]==resource[2]).ok_or("length index absent")?[1].as_u64().ok_or("invalid length index")?;
            if ordered.insert(index,*name).is_some(){return Err("duplicate runtime-array length index".into());}
        }
        let mut replacement="struct _mslBufferSizes {\n    uint zgta_reserved_zero[4];\n".to_owned();
        for index in 0..=(*ordered.keys().last().ok_or("empty sizes struct")?) {
            if let Some(name)=ordered.get(&index){replacement+=&format!("    uint {name};\n");}
            else {replacement+=&format!("    uint zgta_unused_size{index};\n");}
        }
        replacement+="};";
        source.replace_range(begin..end,&replacement);
    }
    let target=format!("s_{}_stipple",reflection["h"].as_str().ok_or("shader hash missing")?);
    let signature=format!(" {entry}(");
    if source.matches(&signature).count()!=1 {return Err("entry signature ambiguous".into());}
    source=source.replacen(&signature,&format!(" {target}("),1);
    // Each source is compiled as an individual library; helpers need no global
    // cross-library namespace and resources keep the original reflection slots.
    Ok(source)
}

fn main() -> Result<(),Box<dyn std::error::Error>> {
    let args:Vec<_>=env::args().collect();
    if args.len()!=4 {return Err("usage: zgta-stipple-msl <packed-shader-dir> <reflection.jsonl> <output.jsonl>".into());}
    let root=Path::new(&args[1]);
    let index:Value=serde_json::from_slice(&fs::read(root.join("index.json"))?)?;
    let reflection=fs::read_to_string(&args[2])?;
    let mut packs=BTreeMap::<u64,Vec<u8>>::new();
    let mut output=String::new();let mut failed=Vec::new();let mut total=0;
    for line in reflection.lines().filter(|l|!l.trim().is_empty()) {
        let rec:Value=serde_json::from_str(line)?;if rec["st"]!="ps"{continue;}total+=1;
        let hash=rec["h"].as_str().ok_or("shader hash absent")?;
        let offsets=index[hash]["p"].as_array().ok_or("shader pack absent")?;
        let pack=offsets[0].as_u64().ok_or("pack number absent")?;
        if !packs.contains_key(&pack){let file=index["_packs"][pack as usize]["file"].as_str().ok_or("pack file absent")?;packs.insert(pack,fs::read(root.join(file))?);}
        let offset=offsets[1].as_u64().ok_or("offset absent")? as usize;
        let bytes=offsets[2].as_u64().ok_or("length absent")? as usize;
        let data=packs[&pack].get(offset..offset.checked_add(bytes).ok_or("offset overflow")?).ok_or("pack shorter than index")?;
        let result=std::str::from_utf8(data).map_err(|e|e.to_string()).and_then(|text|translate(text,&rec));
        match result { Ok(source)=>{output+=&json!({"h":hash,"source":source}).to_string();output.push('\n');},Err(error)=>failed.push(format!("{hash}: {error}")) }
    }
    if !failed.is_empty(){fs::write(format!("{}.errors.txt",args[3]),failed.join("\n"))?;return Err(format!("{} of {total} PS failed; no output published",failed.len()).into());}
    fs::write(&args[3],output.as_bytes())?;
    println!("validated/transpiled {total} PS; {} MSL source bytes; Metal device compilation still required",output.len());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bayer_has_exact_coverage_for_every_level() {
        let mut values=Vec::new();
        for y in 0..4u32 {for x in 0..4u32 {
            let low=(((x^y)&1)<<1)|(y&1);
            let high=((((x^y)>>1)&1)<<1)|(y>>1);
            values.push(4*low+high);
        }}
        values.sort();assert_eq!(values,(0..16).collect::<Vec<_>>());
        for level in 1..16 {assert_eq!(values.iter().filter(|&&v|v<level).count(),level as usize);}
    }
    #[test]
    fn phase_masks_match_original_float4_selection_and_complement() {
        let table: Vec<u16> = [vec![0;2],vec![0x000f;9],vec![0xf00f;9],vec![0xf0ff;6],vec![0xffff;6]].concat();
        for alpha in 0..256 { for invert in [false,true] {
            let raw = table[alpha >> 3] ^ if invert {0xffff} else {0};
            let phases = (0..4).fold(0u32,|m,k|m|((((raw>>(4*k))&15)==15) as u32)<<k);
            let complement = phases ^ 15;
            for y in 0..8 { for x in 0..8 {
                let phase=(x&1)+2*(y&1);
                let selected=((raw>>(4*phase))&15) as f32 / 15.0;
                assert_eq!(selected>=1.0, ((phases>>phase)&1)!=0);
                assert_ne!(((phases>>phase)&1)!=0, ((complement>>phase)&1)!=0);
            }}
        }}
    }
    #[test]
    fn existing_position_and_new_position_both_validate() {
        for original in ["@fragment fn main() -> @location(0) vec4<f32> { return vec4<f32>(1.0); }",
                         "@fragment fn main(@builtin(position) p: vec4<f32>) -> @location(0) vec4<f32> { return p; }"] {
            let record=json!({"h":"abc","res":[],"alen":[]});
            let source=translate(original,&record).unwrap();
            assert!(source.contains("[[function_constant(0)]]"));
            assert!(source.contains("s_abc_stipple("));
            assert!(source.contains("return zgta_stipple_level;"));
            assert!(source.contains("& 16u"), "exact phase branch must survive translation");
            assert!(source.contains("& 15u"));
            assert!(source.contains("zgta_stipple_phase"));
        }
    }
    #[test]
    fn binding_group_is_preserved_and_tint_locations_are_used() {
        let original="struct C { v: vec4<u32> } @group(1) @binding(15) var<uniform> c: C; @fragment fn main(@location(7) v: vec4<f32>) -> @location(0) vec4<f32> { return v * f32(c.v.x); }";
        let source=translate(original,&json!({"h":"abc","res":[["ubo",15,14,"","float",0,16]],"alen":[]})).unwrap();
        assert!(source.contains("[[buffer(14)]]"));
        assert!(source.contains("user(locn7)"));
    }
    #[test]
    fn runtime_sizes_follow_reflection_not_global_order() {
        let original="@group(1) @binding(177) var<storage,read_write> counter: atomic<u32>; @group(1) @binding(161) var<storage,read> data: array<u32>; @fragment fn main() -> @location(0) vec4<f32> { let i=atomicAdd(&counter,1u); return vec4<f32>(f32(data[i])); }";
        let source=translate(original,&json!({"h":"abc","res":[["rw",177,16,"","float",0,4],["ro",161,17,"","float",0,4]],"alen":[[16,0],[17,1]]})).unwrap();
        assert!(source.contains("uint zgta_reserved_zero[4];\n    uint zgta_unused_size0;"));
        assert!(source.contains("[[buffer(15)]]"));
    }
    #[test]
    fn malformed_or_reserved_source_is_rejected() {
        assert!(stipple("@fragment fn main(").is_err());
        assert!(stipple("// zgta_stipple_level").is_err());
    }
}
