// Runs a Workflow script of indexer/scripts/review/ with simulated agents and prints what it did as JSON, so
// test_independent_review.py can assert on it. Usage: node review_harness.mjs SCRIPT
import { player } from './workflow_sim.mjs'

const { failing, scenario, out } = player(process.argv[2])

const objection = (point, where, severity) => ({ point, where, evidence: 'e', severity, check: 'c' })
const review = (verdict, objections) => ({ verdict, objections, not_checked: [] })

await scenario('plan',
  { kind: 'plan', repo: '/r', target: '/r/plan.md', conclusion: '/r/synth.md', data: ['/d/a.json'], scratch: '/s' },
  async (p, o) => (o.phase === 'Review'
    ? { ...review('weakened', [objection('a', 'x.py:1', 'blocking'), objection('b', 'y.py:2', 'minor')]), what_would_change_my_mind: ['w'] }
    : { confirmed: true, how: 'saw it' }))

const diffAgents = async (p, o) => {
  if (o.label === 'review:correctness') return review('weakened', [objection('wrong cond', 'a.py:10', 'significant')])
  if (o.label === 'review:rules') return review('refuted', [objection('module too long', 'a.py:10', 'blocking'), objection('private name', 'b.md:3', 'significant')])
  if (o.label === 'review:losses') return null
  return { confirmed: false, how: 'did not reproduce' }
}
await scenario('diff', { kind: 'diff', repo: '/r', target: 'main...HEAD', criterion: '/r/c.md', verify: 'all', maxVerify: 1, effort: 'low', verifyEffort: 'high' }, diffAgents)
await scenario('diffDefaults', { kind: 'diff', repo: '/r', target: 'main...HEAD' }, diffAgents)
await scenario('verifyNone', { kind: 'diff', repo: '/r', target: 'main...HEAD', verify: 'none' }, diffAgents)
await scenario('verifyAll', { kind: 'diff', repo: '/r', target: 'main...HEAD', verify: 'all' },
  async (p, o) => (o.label === 'review:correctness'
    ? review('weakened', [objection('wrong cond', 'a.py:10', 'significant'), objection('loose wording', 'c.py:1', 'minor')])
    : diffAgents(p, o)))
await scenario('verifierSilent', { kind: 'diff', repo: '/r', target: 'main...HEAD' },
  async (p, o) => (o.phase === 'Verify' ? null : diffAgents(p, o)))
await scenario('mergeOrder', { kind: 'diff', repo: '/r', target: 'main...HEAD', verify: 'none' },
  async (p, o) => (o.label === 'review:correctness'
    ? review('refuted', [objection('first, blocking', 'm.py:1', 'blocking'), objection('tie, first', 'n.py:2', 'minor'), objection('same point', 's.py:3', 'minor')])
    : o.label === 'review:rules'
      ? review('weakened', [objection('later, significant', 'm.py:1', 'significant'), objection('tie, second', 'n.py:2', 'minor'), objection('same point', 's.py:3', 'minor')])
      : review('holds', [])))
await scenario('maxVerifyZero', { kind: 'diff', repo: '/r', target: 'main...HEAD', maxVerify: 0 }, diffAgents)
await scenario('emptyWhere', { kind: 'diff', repo: '/r', target: 'main...HEAD' },
  async (p, o) => (o.phase === 'Verify' ? { confirmed: false, how: 'x' }
    : o.label === 'review:correctness' ? review('refuted', [objection('no pointer given', '', 'blocking')]) : review('holds', [])))
await scenario('holds', { kind: 'diff', repo: '/r', target: 'main...HEAD' }, async () => review('holds', []))
await scenario('customLenses', 
  { kind: 'diff', repo: '/r', target: 'main...HEAD', lenses: [{ key: 'only', focus: 'FOCUS-TEXT' }] },
  async () => review('holds', []))
await scenario('customRules', { kind: 'diff', repo: '/r', target: 'main...HEAD', rules: 'CUSTOM-RULES' }, async () => review('holds', []))

out.missingKind = await failing({ repo: '/r', target: 'x' })
out.missingRepo = await failing({ kind: 'diff', target: 'x' })
out.missingTarget = await failing({ kind: 'diff', repo: '/r' })
out.badKind = await failing({ kind: 'both', repo: '/r', target: 'x' })

console.log(JSON.stringify(out))
