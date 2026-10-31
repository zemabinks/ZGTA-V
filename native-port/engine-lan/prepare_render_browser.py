"""Final render hooks, after the feature/safety/OPEN-RPF browser stages."""
import argparse
from pathlib import Path
import json
from package_portable import checked_runtime
from upgrade_render_runtime import APP,transform_files,write_stage


def stage(previous,output):
    previous,output=previous.absolute(),output.absolute()
    if output.parent!=APP.absolute()/'Build' or output.exists() or any(p.is_symlink() for p in (previous,output,*output.parents)):
        raise ValueError('Separate existing and new regular Build stages required')
    proof=checked_runtime(previous)
    names=set(proof['staged_hashes'])|{'engine-lan-module.js','engine-lan-module.json','browser-stage.json','game.engine-lan.wasm'}
    files={name:(previous/name).read_bytes() for name in names}
    return write_stage(transform_files(files),output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(stage(a.previous,a.output),indent=2))
