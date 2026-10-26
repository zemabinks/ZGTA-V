"""Report renderer startup failure without changing its drain or save lifecycle."""
from stage_browser import once

MARK = '/* ZGTA_GRAPHICS_STATUS_V1 */'
PAGE_ANCHOR = "if (m.gpuLost) { hud.textContent = 'The graphics device was lost (' + m.gpuLost + '): the screen will stay black. Reload the page.'; hud.style.color = '#f66'; return; }"
PAGE_HANDLER = MARK + '''
        const gpuLost=Object.prototype.hasOwnProperty.call(m,'gpuLost') && m.gpuLost !== false;
        if (m.gpuInitFailed || gpuLost) {
            window.ZemaGameReady=false;
            if (!document.getElementById('zema-graphics-failure')) {
                const card=document.createElement('section');card.id='zema-graphics-failure';card.setAttribute('role','alert');
                card.style.cssText='position:fixed;inset:20% auto auto 50%;transform:translateX(-50%);width:min(480px,85vw);padding:24px;z-index:4000;color:#fff;background:#192823;border:1px solid #74c4a0;border-radius:16px;font:16px/1.5 system-ui';
                const title=document.createElement('h2');title.textContent=m.gpuInitFailed?'Graphics could not start':'Graphics device disconnected';
                const detail=document.createElement('p');detail.textContent='Return to the launcher and press Play to try again. Your saved games are kept.';
                const back=document.createElement('a');back.href='/';back.textContent='Back to launcher';back.style.cssText='display:inline-block;padding:10px 16px;color:#10231c;background:#9adfba;border-radius:8px';
                card.append(title,detail,back);document.body.append(card);
            }
            return;
        }
        if (document.getElementById('zema-graphics-failure')) return;
'''
WORKER_ANCHOR = "logLine('init failed: ' + (e && e.stack || e));"
WORKER_REPORT = MARK + '''
        // Keep the upstream drain alive: stopping producers here can interrupt IO.
        // Send only a status flag; detailed driver errors remain in the local log.
        if (!isNode) {
            let failureChannel;
            try {
                failureChannel=new BroadcastChannel(ZemaLaunchChannels.name('game-progress'));
                failureChannel.postMessage({gpuInitFailed:true});
            } catch (_) {} finally { failureChannel?.close(); }
        }
'''


# Loss diagnostics may be empty; the status must not depend on diagnostic text.
# Expected device destruction stays silent, and the original local log is kept.
LOSS_ANCHOR = r"if (!isNode && info.reason !== 'destroyed') new BroadcastChannel(ZemaLaunchChannels.name('game-progress')).postMessage({ gpuLost: info.message.split('\n')[0].slice(0, 160) });"
LOSS_REPORT = """if (!isNode && info.reason !== 'destroyed') {
            let lossChannel;
            try {
                lossChannel=new BroadcastChannel(ZemaLaunchChannels.name('game-progress'));
                lossChannel.postMessage({gpuLost:true});
            } catch (_) {} finally { lossChannel?.close(); }
        }"""


def page(text):
    if MARK in text:
        raise ValueError('Graphics status already applied')
    return once(text, PAGE_ANCHOR, PAGE_HANDLER)


def worker(name, data):
    if name != 'wgpu_worker.js':
        return data
    text = data.decode()
    if MARK in text:
        raise ValueError('Graphics status already applied')
    if '/* ZGTA_LAUNCH_CHANNELS_V1 */' not in text:
        raise ValueError('Graphics status requires scoped channels')
    text = once(text, LOSS_ANCHOR, LOSS_REPORT)
    return once(text, WORKER_ANCHOR, WORKER_ANCHOR + '\n' + WORKER_REPORT).encode()
