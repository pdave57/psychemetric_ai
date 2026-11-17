import { useEffect, useRef, useState, useCallback } from 'react';
import logo from './assets/logo.png';
import {
  startAssessment,
  submitAnswer,
  completeAssessment,
  streamQuestions,
  type AssessmentStartRequest,
} from './api';
import { useAuth } from './context/AuthContext';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import './App.css';

type View = 'intro' | 'quiz' | 'result';

interface TemperamentResult {
  dominant: string;
  summary?: string;
  scores?: Record<string, number>;
}

function AssessmentApp() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [view, setView] = useState<View>('intro');
  const [questions, setQuestions] = useState<Array<{ id: string; text: string; options: Array<{ id: string; text: string }> }>>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TemperamentResult | null>(null);
  const [loading, setLoading] = useState(false);

  const controllerRef = useRef<ReturnType<typeof streamQuestions> | null>(null);
  const runIdRef = useRef(0);

  const reset = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    setQuestions([]);
    setAnswers({});
    setIndex(0);
    setSessionId(null);
    setError(null);
    setResult(null);
    setView('intro');
    setLoading(false);
    runIdRef.current += 1;
  }, []);

  useEffect(() => {
    return () => {
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, []);

  const handleStart = async () => {
    runIdRef.current += 1;
    const runId = runIdRef.current;
    setError(null);
    setLoading(true);

    try {
      const body: AssessmentStartRequest = {
        user_id: `user_${Date.now()}`,
        instrument_code: 'psychemetre_temperament_40',
        instrument_version: '1.0.0',
      };

      const data = await startAssessment(body);
      const sid = ((data as any).session_id || (data as any).id) as string;
      if (!sid) throw new Error('No session id returned from server');

      setSessionId(sid);
      setAnswers({});
      setIndex(0);
      setView('quiz');
      setLoading(false);

      // Pre-populate questions if returned immediately in the start response
      const rawQs = (data as any).questions;
      if (Array.isArray(rawQs) && rawQs.length > 0) {
        setQuestions(
          rawQs.map((q: any) => ({
            id: String(q.id),
            text: q.text ?? '',
            options: Array.isArray(q.options) && q.options.length > 0
              ? q.options.map((opt: any, i: number) => ({
                  id: String(opt.value ?? (i + 1)),
                  text: opt.text ?? opt.label ?? opt.code ?? '',
                }))
              : [
                  { id: '1', text: 'Strongly disagree' },
                  { id: '2', text: 'Disagree' },
                  { id: '3', text: 'Neutral' },
                  { id: '4', text: 'Agree' },
                  { id: '5', text: 'Strongly agree' },
                ],
          }))
        );
      } else {
        setQuestions([]);
      }

      openStream(sid, runId);
    } catch (err) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Failed to start assessment');
    }
  };

  const openStream = (sid: string, runId: number) => {
    setError(null);
    const qtextEl = document.getElementById('qtext');
    if (qtextEl) {
      qtextEl.textContent = 'Connecting to Agent Bleu…';
      qtextEl.classList.add('streaming');
    }

    controllerRef.current = streamQuestions(
      sid,
      (event) => {
        if (runId !== runIdRef.current) return;

        if (event.type === 'question') {
          const rawOpts = (event.options as any[]) || [];
          const opts = rawOpts.length > 0
            ? rawOpts.map((opt: any, i: number) => ({
                id: String(opt.value ?? (i + 1)),
                text: opt.text ?? opt.label ?? opt.code ?? '',
              }))
            : [
                { id: '1', text: 'Strongly disagree' },
                { id: '2', text: 'Disagree' },
                { id: '3', text: 'Neutral' },
                { id: '4', text: 'Agree' },
                { id: '5', text: 'Strongly agree' },
              ];

          setQuestions((prev) => {
            const existing = prev.find((q) => q.id === String(event.id));
            if (existing) {
              return prev.map((q) =>
                q.id === String(event.id)
                  ? {
                      ...q,
                      text: event.text || q.text,
                      options: q.options.length > 0 ? q.options : opts,
                    }
                  : q,
              );
            }
            return [
              ...prev,
              {
                id: String(event.id),
                text: event.text ?? '',
                options: opts,
              },
            ];
          });
        } else if (event.type === 'option') {
          setQuestions((prev) =>
            prev.map((q) => {
              if (q.id !== String(event.question_id)) return q;
              const existingOpt = q.options.find((o) => o.id === String(event.id));
              if (existingOpt) return q;
              return {
                ...q,
                options: [...q.options, { id: String(event.id), text: event.text ?? '' }],
              };
            }),
          );
        } else if (event.type === 'done' || event.type === 'complete') {
          const qtextEl = document.getElementById('qtext');
          if (qtextEl) {
            qtextEl.classList.remove('streaming');
          }
        }
      },
      () => {
        if (runId !== runIdRef.current) return;
        const qtextEl = document.getElementById('qtext');
        if (qtextEl) {
          qtextEl.classList.remove('streaming');
        }
      },
    );
  };

  const currentQuestion = questions[index];

  const handleChoose = (optId: string) => {
    if (!currentQuestion) return;
    setAnswers((prev) => ({ ...prev, [currentQuestion.id]: optId }));
  };

  const analyseLocally = () => {
    const totals: Record<string, number> = { Sanguine: 0, Choleric: 0, Melancholic: 0, Phlegmatic: 0 };
    const counts: Record<string, number> = { Sanguine: 0, Choleric: 0, Melancholic: 0, Phlegmatic: 0 };

    questions.forEach((q, i) => {
      const val = parseInt(answers[q.id] || '3', 10);
      let dim = 'Sanguine';
      const code = ((q as any).code || '').toUpperCase();
      if (code.startsWith('SAN') || (!code && i < 10)) dim = 'Sanguine';
      else if (code.startsWith('CHO') || (!code && i < 20)) dim = 'Choleric';
      else if (code.startsWith('MEL') || (!code && i < 30)) dim = 'Melancholic';
      else if (code.startsWith('PHL') || (!code && i < 40)) dim = 'Phlegmatic';

      const reverse = (q as any).reverse_coded || (code && (code.endsWith('04') || code.endsWith('08')));
      const score = reverse ? (6 - val) : val;
      totals[dim] += score;
      counts[dim] += 1;
    });

    const scores: Record<string, number> = {};
    for (const dim of ['Sanguine', 'Choleric', 'Melancholic', 'Phlegmatic']) {
      const count = counts[dim] || 10;
      const mean = (totals[dim] || 30) / count;
      scores[dim] = Math.max(0, Math.min(100, Math.round(((mean - 1) / 4) * 100)));
    }

    const dominant = Object.keys(scores).sort((a, b) => scores[b] - scores[a])[0] || 'Sanguine';
    const TEMPERAMENT_SUMMARIES: Record<string, string> = {
      Sanguine: 'Expressive, optimistic and quick to connect. You recharge around people and bring energy to a room.',
      Choleric: 'Driven, decisive and direct. You set goals fast and move others toward them.',
      Melancholic: 'Thoughtful, precise and deeply reflective. You notice detail and hold high standards.',
      Phlegmatic: 'Calm, steady and dependable. You keep your balance when others lose theirs.',
    };

    return {
      dominant,
      summary: TEMPERAMENT_SUMMARIES[dominant] || '',
      scores,
    };
  };

  const handleNext = async () => {
    if (!currentQuestion) return;

    const answered = answers[currentQuestion.id];
    if (!answered) return;

    // Submit current answer to the backend
    try {
      await submitAnswer(sessionId!, {
        question_id: currentQuestion.id,
        value: parseInt(answered, 10),
      });
    } catch (e) {
      console.warn('Failed to save answer incrementally', e);
    }

    const last = index === questions.length - 1;

    if (!last) {
      setIndex((i) => i + 1);
      return;
    }

    setLoading(true);
    try {
      // Ensure all answers in answers state are submitted
      for (const [qid, val] of Object.entries(answers)) {
        if (qid !== currentQuestion.id) {
          try {
            await submitAnswer(sessionId!, {
              question_id: qid,
              value: parseInt(val, 10),
            });
          } catch {
            // continue
          }
        }
      }

      const data = await completeAssessment(sessionId!);
      const resultData = data as TemperamentResult & { [key: string]: unknown };

      const scoresMap: Record<string, number> = {};
      const rawScores = (resultData as any).temperament_scores;
      if (Array.isArray(rawScores)) {
        for (const item of rawScores) {
          const name = item.dimension ? (item.dimension.charAt(0).toUpperCase() + item.dimension.slice(1)) : 'Score';
          scoresMap[name] = Math.round(item.normalized_score ?? item.score ?? 0);
        }
      } else if (resultData.scores && typeof resultData.scores === 'object') {
        Object.assign(scoresMap, resultData.scores);
      }

      const dominant =
        resultData.dominant ??
        (Array.isArray((resultData as any).leading_tendencies) && (resultData as any).leading_tendencies[0]
          ? ((resultData as any).leading_tendencies[0].charAt(0).toUpperCase() + (resultData as any).leading_tendencies[0].slice(1))
          : resultData.temperament ?? 'Unknown');

      const TEMPERAMENT_SUMMARIES: Record<string, string> = {
        Sanguine: 'Expressive, optimistic and quick to connect. You recharge around people and bring energy to a room.',
        Choleric: 'Driven, decisive and direct. You set goals fast and move others toward them.',
        Melancholic: 'Thoughtful, precise and deeply reflective. You notice detail and hold high standards.',
        Phlegmatic: 'Calm, steady and dependable. You keep your balance when others lose theirs.',
      };

      setResult({
        dominant,
        summary: resultData.summary || TEMPERAMENT_SUMMARIES[dominant] || '',
        scores: scoresMap,
      });
      setError(null);
      setView('result');
    } catch (err) {
      console.warn('Backend completeAssessment failed, calculating result locally:', err);
      // Fallback: calculate result from submitted answers so user always sees their result
      const localResult = analyseLocally();
      setResult(localResult);
      setError(null);
      setView('result');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    if (index > 0) setIndex((i) => i - 1);
  };

  const handleRestart = () => {
    reset();
  };

  const handleLogout = () => {
    reset();
    logout();
    navigate('/login');
  };

  return (
    <div className="app">
      <header className="header">
        <img src={logo} alt="Agent Bleu" className="header-logo" />
      </header>

      <main className="wrap">
        {error && (
          <div className="err" role="alert">
            {error}
            <button className="btn ghost" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        )}

        <section id="intro" className={`intro ${view === 'intro' ? '' : 'hidden'}`}>
          <h1>Answer a few questions. Agent Bleu reads your personality.</h1>
          <p>
            Each question has no right or wrong answer. Pick the response closest to your
            first instinct.
          </p>
          {loading ? (
            <button className="btn" disabled>Connecting…</button>
          ) : (
            <button className="btn" id="start" onClick={handleStart}>Start</button>
          )}
        </section>

        <section
          id="quiz"
          className={`quiz ${view === 'quiz' ? '' : 'hidden'}`}
        >
          <div className="bar">
            <div className="meta">
              <div className="track" id="track" aria-hidden="true">
                {questions.map((_, i) => (
                  <i key={i} className={i <= index ? 'done' : ''} />
                ))}
              </div>
              <div className="count" id="count" aria-live="polite">
                {questions.length > 0 ? `${index + 1} of ${questions.length}` : ''}
              </div>
            </div>
          </div>
          <div id="notice"></div>
          {currentQuestion ? (
            <>
              <h2 className="q-text" id="qtext">{currentQuestion.text}</h2>
              <div className="options" id="options" role="radiogroup" aria-labelledby="qtext">
                {currentQuestion.options.map((opt, i) => {
                  const selected = answers[currentQuestion.id] === opt.id;
                  return (
                    <button
                      key={opt.id}
                      className="opt"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => handleChoose(opt.id)}
                    >
                      <kbd>{i + 1}</kbd>
                      <span>{opt.text}</span>
                    </button>
                  );
                })}
              </div>
              <div className="actions">
                <button className="btn ghost" id="back" onClick={handleBack} disabled={index === 0}>
                  Back
                </button>
                <button
                  className="btn"
                  id="next"
                  disabled={!answers[currentQuestion.id] || loading}
                  onClick={handleNext}
                >
                  {index === questions.length - 1
                    ? loading
                      ? 'Analysing…'
                      : 'See my result'
                    : 'Next question'}
                </button>
              </div>
              <p className="note">Tip: select your answer to continue.</p>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
              <h2 className="q-text" id="qtext">Connecting to Agent Bleu…</h2>
              <p className="note">Streaming assessment questions…</p>
            </div>
          )}
        </section>

        <section
          id="result"
          className={`result ${view === 'result' ? '' : 'hidden'}`}
        >
          <div className="bar"></div>
          {result ? (
            <>
              <p className="count">Your dominant temperament</p>
              <h2 id="rname">{result.dominant}</h2>
              <p className="lead" id="rsummary">{result.summary ?? ''}</p>
              <div className="scores" id="scores">
                {result.scores &&
                  Object.entries(result.scores).map(([k, v]) => (
                    <div key={k} className="score">
                      <span>{k}</span>
                      <div className="meter"><b data-w={v} style={{ width: `${v}%` }}></b></div>
                      <span>{v}%</span>
                    </div>
                  ))}
              </div>
            </>
          ) : null}
          {result && (
            <button className="btn ghost" id="restart" onClick={handleRestart}>
              Retake analysis
            </button>
          )}
        </section>

        <button className="btn ghost" onClick={handleLogout} style={{ marginTop: '2rem', display: 'block', margin: '2rem auto 0' }}>
          Sign out
        </button>
      </main>
    </div>
  );
}

function App() {
  const { loading, authenticated } = useAuth();

  if (loading) {
    return (
      <div className="app">
        <header className="header">
          <img src={logo} alt="Agent Bleu" className="header-logo" />
        </header>
        <main className="wrap" style={{ textAlign: 'center', paddingTop: '4rem' }}>
          <p>Loading…</p>
        </main>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/"
          element={
            authenticated ? <AssessmentApp /> : <Navigate to="/login" replace />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
