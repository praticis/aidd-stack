// Runs indexer/scripts/review/research-round.js with simulated agents and prints what it did as JSON, so
// test_research_round.py can assert on it. Usage: node research_harness.mjs SCRIPT
import { player } from './workflow_sim.mjs'

const { failing, scenario, out } = player(process.argv[2])

const report = (id) => ({ question: id, answer: `answer ${id}`, evidence: [{ claim: 'c', how_verified: 'h' }], recommendation: 'keep-plan', not_verified: ['n'] })
const Q = (id, extra = {}) => ({ id, prompt: `PROMPT-${id}`, ...extra })
const base = { repo: '/r', plan: '/r/plan.md' }
const agents = async (p, o) => {
  if (o.phase === 'Research') return report(o.label.replace('research:', ''))
  if (o.label === 'synthesis') return { decision: 'amend-plan', rationale: 'SYNTH-RATIONALE', amended_plan_items: ['i'] }
  return { verdict: 'weakened', objections: [{ point: 'p', evidence: 'e', severity: 'minor' }] }
}

await scenario('full', {
  ...base, questions: [Q('a', { kind: 'web' }), Q('b', { kind: 'measure', budget: 20 }), Q('c')],
  context: ['/r/parent.md'], scratch: '/s', tools: 'TOOLS-HERE', docker: true,
}, agents)
await scenario('plain', { ...base, questions: [Q('a')] }, agents)
await scenario('silent', { ...base, questions: [Q('a'), Q('b')] }, async (p, o) => (o.label === 'research:b' ? null : agents(p, o)))
await scenario('reportsOnly', { ...base, questions: [Q('a')], synthesize: false }, agents)
await scenario('noChallenge', { ...base, questions: [Q('a')], challenge: false }, agents)
await scenario('efforts', { ...base, questions: [Q('a')], effort: 'low', synthEffort: 'medium', challengeEffort: 'xhigh' }, agents)
await scenario('customRules', { ...base, questions: [Q('a')], rules: 'CUSTOM-RULES' }, agents)
await scenario('five', { ...base, questions: ['a', 'b', 'c', 'd', 'e'].map((i) => Q(i)), allowMore: true }, agents)

out.noRepo = await failing({ plan: '/p', questions: [Q('a')] })
out.noPlan = await failing({ repo: '/r', questions: [Q('a')] })
out.noQuestions = await failing({ ...base, questions: [] })
out.tooMany = await failing({ ...base, questions: ['a', 'b', 'c', 'd', 'e'].map((i) => Q(i)) })
out.noPrompt = await failing({ ...base, questions: [{ id: 'a' }] })
out.dupId = await failing({ ...base, questions: [Q('a'), Q('a')] })
out.badKind = await failing({ ...base, questions: [Q('a', { kind: 'guess' })] })

console.log(JSON.stringify(out))
