// Plays the agents for a Workflow script of indexer/scripts/review/, and records what the script asked of them.
//   const { run, failing, scenario, out } = player(scriptPath)
// run(args, agentImpl) returns { result, logs, calls }; scenario(name, args, agentImpl) stores it in `out`, or { crashed }
// when the script throws, so that a crash fails the tests of that scenario only.
import fs from 'node:fs'

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

export const player = (scriptPath) => {
  const src = fs.readFileSync(scriptPath, 'utf8').replace(/export const meta =/, 'const meta =')
  const out = {}
  const run = async (args, agentImpl) => {
    const logs = []
    const calls = []
    const fn = new AsyncFunction('args', 'agent', 'parallel', 'log', 'phase', 'budget', src)
    const agent = async (prompt, opts) => {
      calls.push({ label: opts.label, phase: opts.phase, schema: !!opts.schema, effort: opts.effort, prompt })
      return agentImpl(prompt, opts)
    }
    // the Workflow tool's own semantics: a thunk that throws resolves to null
    const parallel = (thunks) => Promise.all(thunks.map(async (t) => { try { return await t() } catch { return null } }))
    const result = await fn(args, agent, parallel, (m) => logs.push(m), () => {}, { total: null })
    return { result, logs, calls }
  }
  const failing = async (args) => {
    try { await run(args, async () => null); return null } catch (e) { return e.message }
  }
  const scenario = async (name, args, impl) => {
    try { out[name] = await run(args, impl) } catch (e) { out[name] = { crashed: e.message } }
  }
  return { run, failing, scenario, out }
}
