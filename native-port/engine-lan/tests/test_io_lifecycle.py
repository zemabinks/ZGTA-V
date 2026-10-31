from pathlib import Path
from public_test_inputs import game_file
import hashlib,json,os,subprocess,sys,tempfile,unittest
ROOT=Path(os.environ.get('ZGTA_SOURCE_ROOT',Path(__file__).resolve().parents[1]));HERE=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(HERE),str(ROOT)]
import io_lifecycle as fix,stage_browser,serve_browser,launch_channels,ui_asset_refresh
MIRROR=game_file('')

BLOCK="\n    if name == 'io_worker.js':\n        import io_lifecycle\n        text = io_lifecycle.apply(text)"
def load_public(module,source,variant):
    # Execute the complete actual module source, preserving its root path and
    # __main__ guard. Public functions are not independently reconstructed.
    scope={'__file__':module.__file__,'__name__':'qa_'+variant+'_'+module.__name__}
    exec(compile(source,module.__file__,'exec'),scope)
    return type('PublicModule',(),scope)

def modules_under_review():
    sources={module.__name__:Path(module.__file__).read_text() for module in [stage_browser,serve_browser]}
    baseline={name:text.replace(BLOCK,'') for name,text in sources.items()}
    proposal_patch=HERE/'integration.patch'
    if proposal_patch.exists():
        # Apply the delivered exact patch to copies, then exercise complete
        # patched modules through their actual public entry points.
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'native-port/engine-lan';target.mkdir(parents=True)
            for module in [stage_browser,serve_browser]:(target/Path(module.__file__).name).write_text(baseline[module.__name__])
            run=subprocess.run(['git','apply',str(proposal_patch)],cwd=folder,capture_output=True,text=True)
            if run.returncode:raise AssertionError(run.stdout+run.stderr)
            proposed={module.__name__:(target/Path(module.__file__).name).read_text() for module in [stage_browser,serve_browser]}
    else:
        # Once copied into the repository, test the actual integrated modules.
        proposed=sources
    for name,text in proposed.items():
        if text.count(BLOCK)!=1:raise AssertionError('One actual public-function integration required: '+name)
    old=[load_public(m,baseline[m.__name__],'baseline')for m in [stage_browser,serve_browser]]
    new=[load_public(m,proposed[m.__name__],'proposed')for m in [stage_browser,serve_browser]]
    return old,new

def fragments(text):
    a=text.index('let storeClosing = false;') if fix.MARK in text else text.index('async function openStore(version) {')
    b=text.index('// ---- boot read set',a)
    c=text.index('let ready = null');d=text.index('// The page tells us',c)
    e=text.index("new BroadcastChannel(ZemaLaunchChannels.name('game-io'))");f=text.index('// ---- the engine',e)
    g=text.index('self.onmessage = async (ev) =>');h=text.index('self.postMessage({ loaded: true });',g)
    return text[a:b]+text[c:d]+text[e:f]+text[g:h]

class IOLifecycle(unittest.TestCase):
 def test_prior_fps_insertion_is_not_offline_integration(self):
    source=Path(serve_browser.__file__).read_text().replace(BLOCK,'')
    start=source.index('def fps_transport(');at=source.index('    text=data.decode()',start)
    wrong=source[:at]+source[at:].replace('    text=data.decode()','    text=data.decode()'+BLOCK,1)
    public=load_public(serve_browser,wrong,'prior_wrong_fps')
    raw=(MIRROR/'b/8b0b5899ed/io_worker.js').read_bytes()
    for mode in ['story','sandbox']:
        self.assertNotIn(fix.MARK.encode(),public.offline_worker('io_worker.js',raw,mode))

 def test_refusal_and_composition(self):
    raw=(MIRROR/'b/8b0b5899ed/io_worker.js').read_bytes();text=raw.decode();self.assertEqual(hashlib.sha256(raw).hexdigest(),fix.PIN)
    changed=fix.apply(text)
    for invalid in [text.replace('let ready = null;','let ready = undefined;'),changed,text.replace('const s = await openHandle', 'const x = await openHandle')]:
        with self.assertRaises(ValueError):fix.apply(invalid)
    old,new=modules_under_review();oldpatch=old[0].patch;oldoffline=old[1].offline_worker;patch=new[0].patch;offline=new[1].offline_worker;payload=[]
    for mode in ['lan','story','sandbox']:
        original=oldpatch('io_worker.js',raw) if mode=='lan' else oldoffline('io_worker.js',raw,mode)
        result=patch('io_worker.js',raw) if mode=='lan' else offline('io_worker.js',raw,mode)
        self.assertIn(fix.MARK.encode(),result);self.assertIn(ui_asset_refresh.MARK.encode(),result)
        namespace='zema-engine-lan-userdata-v1' if mode=='lan' else 'zema-browser-'+mode+'-userdata-v1'
        self.assertIn(namespace.encode(),result);self.assertIn(b'readFromStore(id, off, len, dst)',result)
        self.assertNotIn(b'removeEntry(',result)
        worker=launch_channels.worker('io_worker.js',result).decode()
        prior=launch_channels.BOOT+launch_channels.channels(original.decode(),{'game-progress':1,'game-io':1})
        self.assertNotRegex(worker,launch_channels.LITERAL)
        page=serve_browser.index((MIRROR/'index.html').read_bytes(),mode).decode();a=page.index("const bc = new BroadcastChannel(ZemaLaunchChannels.name('game-progress'))");b=page.index('// Between reports',a)
        payload.append({'mode':mode,'proposed':fragments(worker),'original':fragments(prior),'page':page[a:b],'worker_sha256':hashlib.sha256(result).hexdigest(),'served_worker_sha256':hashlib.sha256(worker.encode()).hexdigest()})
        with tempfile.NamedTemporaryFile(suffix='.js') as script:
            script.write(worker.encode());script.flush();subprocess.run(['node','--check',script.name],check=True,capture_output=True)
    with tempfile.TemporaryDirectory() as folder:
        file=Path(folder)/'fixture.json';file.write_text(json.dumps(payload));run=subprocess.run(['node',str(Path(__file__).with_name('io_lifecycle_fixture.cjs')),str(file)],capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr);print(run.stdout.strip())
    if os.environ.get('ZGTA_IO_HASH_RECEIPT'):
        Path(os.environ['ZGTA_IO_HASH_RECEIPT']).write_text(json.dumps([{k:v for k,v in x.items() if k.endswith('sha256')or k=='mode'}for x in payload],indent=2)+'\n')

if __name__=='__main__':unittest.main()
