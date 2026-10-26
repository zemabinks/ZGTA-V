//! Typed FFI to statically compiled game functions, with no VM or JIT.
use std::{ffi::CString, marker::PhantomData, cell::RefCell, collections::HashMap, rc::Rc};

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct NativeValue { pub kind: u32, pub reserved: u32, pub bits: u64 }
#[derive(Clone, Copy, Debug)]
pub enum Val { I32(i32), I64(i64), F32(u32), F64(u64) }
impl Val {
    pub fn unwrap_i64(self) -> i64 { match self { Self::I64(v) => v, Self::I32(v) => v as i64, _ => 0 } }
    fn native(self) -> NativeValue {
        let (kind, bits) = match self { Self::I32(v) => (1, v as u32 as u64), Self::I64(v) => (2, v as u64), Self::F32(v) => (3, v as u64), Self::F64(v) => (4, v) };
        NativeValue { kind, reserved: 0, bits }
    }
    fn from_native(v: NativeValue) -> Option<Self> {
        match v.kind { 1 => Some(Self::I32(v.bits as i32)), 2 => Some(Self::I64(v.bits as i64)), 3 => Some(Self::F32(v.bits as u32)), 4 => Some(Self::F64(v.bits)), 0 => None, _ => None }
    }
}
pub type ValType = u32;
pub struct FuncType { params: Vec<ValType>, result: Option<ValType> }
impl FuncType {
    pub fn params(&self) -> impl Iterator<Item=ValType> + '_ { self.params.iter().copied() }
    pub fn results(&self) -> impl Iterator<Item=ValType> + '_ { self.result.into_iter() }
}
extern "C" {
    fn mugoat_command_info(name: *const std::ffi::c_char, params: *mut u32, capacity: u32, result: *mut u32) -> i32;
    fn mugoat_command_call(instance: *mut std::ffi::c_void, name: *const std::ffi::c_char, args: *const NativeValue, count: u32, result: *mut NativeValue) -> bool;
}
pub struct Caller<'a, T> { pub instance: *mut std::ffi::c_void, marker: PhantomData<&'a mut T> }
pub struct Export(Func);
struct Definition { name: CString, ty: FuncType }
#[derive(Clone)]
pub struct Func(Rc<Definition>);
thread_local! {
    // Immutable signatures belong to the generated engine version. Cache per
    // script thread without a global lock or repeat string/type allocations.
    static EXPORTS: RefCell<HashMap<String, Option<Func>>> = RefCell::new(HashMap::new());
}
impl<'a, T> Caller<'a, T> {
    pub fn new(instance: *mut std::ffi::c_void) -> Self { Self { instance, marker: PhantomData } }
    pub fn get_export(&mut self, name: &str) -> Option<Export> {
        EXPORTS.with(|cache| {
            if let Some(found) = cache.borrow().get(name) { return found.clone().map(Export); }
            let symbol = CString::new(name).ok()?;
            let mut params = [0;32]; let mut result=0;
            let count = unsafe { mugoat_command_info(symbol.as_ptr(),params.as_mut_ptr(),32,&mut result) };
            let found = if count<0 || count as usize>params.len() { None } else {
                Some(Func(Rc::new(Definition { name: symbol, ty: FuncType { params: params[..count as usize].to_vec(), result: (result!=0).then_some(result) } })))
            };
            cache.borrow_mut().insert(name.to_owned(),found.clone());
            found.map(Export)
        })
    }
}
impl Export { pub fn into_func(self) -> Option<Func> { Some(self.0) } }
impl Func {
    pub fn ty<T>(&self, _: &mut Caller<'_, T>) -> &FuncType { &self.0.ty }
    pub fn call<T>(&self, caller: &mut Caller<'_, T>, args: &[Val], output: &mut [Val]) -> anyhow::Result<()> {
        anyhow::ensure!(args.len() == self.0.ty.params.len() && args.len() <= 32, "native argument count mismatch");
        anyhow::ensure!(output.len() == usize::from(self.0.ty.result.is_some()), "native result count mismatch");
        let mut values = [NativeValue::default();32];
        for (index,arg) in args.iter().enumerate() { values[index]=arg.native(); }
        anyhow::ensure!(values.iter().zip(&self.0.ty.params).all(|(v,t)| v.kind==*t), "native argument type mismatch");
        let mut result = NativeValue::default();
        anyhow::ensure!(unsafe { mugoat_command_call(caller.instance, self.0.name.as_ptr(), values.as_ptr(), args.len() as u32, &mut result) }, "native command rejected");
        if let Some(expected) = self.0.ty.result {
            anyhow::ensure!(result.kind == expected, "native result type mismatch");
            output[0] = Val::from_native(result).ok_or_else(|| anyhow::anyhow!("invalid native result"))?;
        }
        Ok(())
    }
}

pub fn coerce_args(args: &[Val], ty: &FuncType) -> Vec<Val> {
    args.iter().zip(ty.params()).map(|(v,t)| match (v,t) {
        (Val::I32(n),2) => Val::I64(*n as i64), (Val::I64(n),1) => Val::I32(*n as i32), _ => *v,
    }).collect()
}
pub fn default_val(t: &ValType) -> Val { match t { 2 => Val::I64(0), 3 => Val::F32(0), 4 => Val::F64(0), _ => Val::I32(0) } }

#[cfg(test)]
mod tests {
    use super::*;
    #[no_mangle]
    extern "C" fn mugoat_command_info(_: *const std::ffi::c_char, p: *mut u32, _: u32, result: *mut u32) -> i32 {
        unsafe { *p = 2; *result = 3; } 1
    }
    #[no_mangle]
    extern "C" fn mugoat_command_call(_: *mut std::ffi::c_void, _: *const std::ffi::c_char, _: *const NativeValue, _: u32, out: *mut NativeValue) -> bool {
        unsafe { *out = NativeValue { kind: 3, reserved: 0, bits: 3.5f32.to_bits() as u64 }; } true
    }
    #[test]
    fn native_abi_coerces_width_and_preserves_float_bits() {
        let mut caller = Caller::<()>::new(std::ptr::null_mut());
        let f = caller.get_export("test").unwrap().into_func().unwrap();
        let args = coerce_args(&[Val::I32(-7)], f.ty(&mut caller));
        assert!(matches!(args[0], Val::I64(-7)));
        let mut out = [Val::F32(0)]; f.call(&mut caller, &args, &mut out).unwrap();
        assert!(matches!(out[0], Val::F32(v) if v == 3.5f32.to_bits()));
        assert!(f.call(&mut caller, &[Val::I32(7)], &mut out).is_err());
        assert!(f.call(&mut caller, &[], &mut out).is_err());
        let cached = caller.get_export("test").unwrap().into_func().unwrap();
        assert!(Rc::ptr_eq(&f.0,&cached.0), "Native signatures should not allocate again each frame");
    }
}
