/* Failed optional audio banks must not strand script requests forever.
 * Adapted from Glue 5 a62e56a5 script_assets.rs:57-79. Each worker owns
 * its own depth; only FAILED (2) inside a script request becomes LOADED (0).
 * The original engine still handles every request and actual bank state.
 */
(function(root){'use strict';
 function callbacks(originalRequest,originalStatus,onFallback){
  if(typeof originalRequest!=='function'||typeof originalStatus!=='function')throw Error('Explicit script bank originals required');
  if(onFallback!==undefined&&typeof onFallback!=='function')throw Error('Script bank observer must be a function');
  let depth=0,noted=false;
  return {
   script_bank_request(bank,overNetwork,players){
    depth++;
    try{return originalRequest(bank,overNetwork,players);}
    finally{depth--;}
   },
   bank_loading_status(slot,bank){
    const status=originalStatus(slot,bank);
    if(status!==2||depth===0)return status;
    if(!noted){noted=true;try{onFallback?.(bank>>>0);}catch{}}
    return 0;
   }
  };
 }
 const api={callbacks};root.ZemaScriptBank=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
