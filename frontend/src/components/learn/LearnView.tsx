import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { LESSONS, lessonCommits } from '../../lib/lessons'
import { ROW_H } from '../graph/GraphEdges'
import { CommitGraph } from '../graph/CommitGraph'

interface Props { hasRepo: boolean; onOpenStrategy: () => void }

const noop = () => {}

export function LearnView({ hasRepo, onOpenStrategy }: Props) {
  const [lessonIdx, setLessonIdx] = useState(0)
  const [step, setStep] = useState(0)
  const lesson = LESSONS[lessonIdx]
  const commits = useMemo(() => lessonCommits(lesson, step), [lesson, step])
  const last = lesson.steps.length - 1

  const pick = (i: number) => { setLessonIdx(i); setStep(0) }

  return (
    <div className="flex h-full min-h-0 fade-in">
      <nav aria-label="Lessons" className="w-64 shrink-0 overflow-y-auto border-r border-line p-3">
        <h2 className="mb-2 px-2 text-[11px] uppercase tracking-wide text-mute">Learn Git branching</h2>
        {LESSONS.map((l, i) => (
          <button key={l.id} onClick={() => pick(i)} aria-current={i === lessonIdx}
            className={`mb-1 block w-full rounded px-2 py-1.5 text-left hover:bg-raised ${i === lessonIdx ? 'bg-raised text-accent' : ''}`}>
            <span className="block font-medium">{l.title}</span>
            <span className="block text-[12px] text-mute">{l.summary}</span>
          </button>
        ))}
      </nav>

      <div className="min-w-0 flex-1 overflow-y-auto p-6">
        <h2 className="text-xl font-semibold">{lesson.title.replace(/^\d+ · /, '')}</h2>
        <div className="mt-2 max-w-2xl space-y-2 text-[14px] leading-relaxed">
          {lesson.body.map((p) => <p key={p}>{p}</p>)}
        </div>

        <section className="mt-5 max-w-3xl overflow-hidden rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-3 py-2 text-[12px] text-mute">
            Illustration — an invented example, not your repository. Newest commit at the top.
          </div>
          <div style={{ height: Math.max(commits.length, 3) * ROW_H + 12 }}>
            <CommitGraph commits={commits} selected={null} highlight={null} hasMore={false}
              loadingMore={false} moreError={null} onSelect={noop} onLoadMore={noop} onClearHighlight={noop} />
          </div>
          <div className="flex items-center gap-3 border-t border-line px-3 py-2">
            <button aria-label="Previous step" disabled={step === 0} onClick={() => setStep(step - 1)}
              className="rounded border border-line p-1 hover:border-accent disabled:opacity-40"><ChevronLeft size={16} /></button>
            <p key={`${lesson.id}-${step}`} className="flex-1 fade-in">{lesson.steps[step].caption}</p>
            <span className="text-mute">Step {step + 1} / {last + 1}</span>
            <button aria-label="Next step" disabled={step === last} onClick={() => setStep(step + 1)}
              className="rounded border border-line p-1 hover:border-accent disabled:opacity-40"><ChevronRight size={16} /></button>
          </div>
        </section>

        <p className="mt-4 max-w-2xl rounded border-l-2 border-accent bg-accent/10 px-3 py-2">
          <b>Takeaway:</b> {lesson.takeaway}
        </p>

        <section className="mt-6 max-w-2xl rounded-lg border border-line bg-panel p-4">
          <h3 className="font-semibold">Compare with your own repository</h3>
          <p className="mt-1 text-mute">
            {hasRepo ? 'See which style your repository resembles, with the evidence behind it.'
              : 'Open one of your own repositories to see its branching strategy and how its history really looks.'}
          </p>
          {hasRepo && (
            <button onClick={onOpenStrategy} className="mt-3 rounded border border-accent bg-accent/10 px-3 py-1.5 text-accent hover:bg-accent/20">
              View my branching strategy
            </button>
          )}
        </section>
      </div>
    </div>
  )
}
