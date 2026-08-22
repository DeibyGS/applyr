import { useEffect, useState } from "react";
import { createIntake, getJob, listIntake, listJobs, IntakeRow, JobDetail, JobSummary } from "./api";

const POLL_INTERVAL_MS = 3000;

function IntakeForm({ onCreated }: { onCreated: () => void }) {
  const [rawText, setRawText] = useState("");
  const [sourceNote, setSourceNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createIntake(rawText, sourceNote);
      setRawText("");
      setSourceNote("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Paste a job offer</h2>
      <textarea
        value={rawText}
        onChange={(e) => setRawText(e.target.value)}
        placeholder="Paste the full job offer text here..."
        rows={8}
        cols={60}
        required
      />
      <br />
      <input
        value={sourceNote}
        onChange={(e) => setSourceNote(e.target.value)}
        placeholder="Source (optional, e.g. LinkedIn)"
      />
      <br />
      <button type="submit" disabled={submitting || !rawText.trim()}>
        {submitting ? "Saving..." : "Add to pending"}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}

function PendingIntakeList({ rows }: { rows: IntakeRow[] }) {
  return (
    <section>
      <h2>Waiting for your agent ({rows.length})</h2>
      <ul>
        {rows.map((row) => (
          <li key={row.id}>
            #{row.id} — {row.raw_text.slice(0, 80)}
            {row.raw_text.length > 80 ? "..." : ""}
            {row.source_note ? ` (${row.source_note})` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}

function JobDetailPanel({ job }: { job: JobDetail }) {
  return (
    <div>
      <h3>
        {job.title} — {job.company}
      </h3>
      <p>
        Status: {job.status} | Compatibility: {job.compatibility_pct}%
      </p>
      <table>
        <thead>
          <tr>
            <th>Topic</th>
            <th>Score</th>
            <th>Confidence</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {job.topics.map((t) => (
            <tr key={t.topic}>
              <td>{t.topic}</td>
              <td>{t.score}</td>
              <td>{t.confidence ?? "—"}</td>
              <td>{t.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JobList({ jobs }: { jobs: JobSummary[] }) {
  const [selected, setSelected] = useState<JobDetail | null>(null);

  async function select(id: number) {
    setSelected(await getJob(id));
  }

  return (
    <section>
      <h2>Jobs ({jobs.length})</h2>
      <ul>
        {jobs.map((job) => (
          <li key={job.id}>
            <button onClick={() => select(job.id)}>
              #{job.id} {job.title} — {job.company} ({job.compatibility_pct}%, {job.status})
            </button>
          </li>
        ))}
      </ul>
      {selected && <JobDetailPanel job={selected} />}
    </section>
  );
}

export default function App() {
  const [pendingIntake, setPendingIntake] = useState<IntakeRow[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);

  async function refresh() {
    const [intakeRows, jobRows] = await Promise.all([listIntake("pending"), listJobs()]);
    setPendingIntake(intakeRows);
    setJobs(jobRows);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <main>
      <h1>applyr ui</h1>
      <IntakeForm onCreated={refresh} />
      <PendingIntakeList rows={pendingIntake} />
      <JobList jobs={jobs} />
    </main>
  );
}
