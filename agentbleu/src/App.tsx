import { useEffect, useRef, useState, useCallback } from 'react';
import logo from './assets/logo.png';
import {
  startAssessment,
  submitAnswer,
  completeAssessment,
  getSessionRecommendations,
  submitRecommendationFeedback,
  streamQuestions,
  streamAssessmentResult,
  fetchAssessmentResult,
  type AssessmentStartRequest,
  type RecommendationItem,
  type AssessmentResult,
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
  narrative?: string;
  motion?: string;
  recommendations?: RecommendationItem[];
  llm_model?: string;
  prompt_version?: string;
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

  /* Live LLM result synthesis */
  const [streaming, setStreaming] = useState(false);
  const [narrativeText, setNarrativeText] = useState('');
  const [motionText, setMotionText] = useState('');
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [reportId, setReportId] = useState<string | null>(null);

  const controllerRef = useRef<ReturnType<typeof streamQuestions> | null>(null);
  const resultStreamRef = useRef<ReturnType<typeof streamAssessmentResult> | null>(null);
  const runIdRef = useRef(0);

  const reset = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    if (resultStreamRef.current) {
      resultStreamRef.current.abort();
      resultStreamRef.current = null;
    }
    setQuestions([]);
    setAnswers({});
    setIndex(0);
    setSessionId(null);
    setError(null);
    setResult(null);
    setStreaming(false);
    setNarrativeText('');
    setMotionText('');
    setRecommendations([]);
    setReportId(null);
    setView('intro');
    setLoading(false);
    runIdRef.current += 1;
  }, []);

  useEffect(() => {
    return () => {
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
      if (resultStreamRef.current) {
        resultStreamRef.current.abort();
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
      narrative: `Your reflective responses indicate prominent tendencies in the ${dominant} dimension. This pattern reflects your unique preferences when engaging with social situations, problem-solving, and personal tasks.`,
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

      const summary = resultData.summary || TEMPERAMENT_SUMMARIES[dominant] || '';

      setResult({
        dominant,
        summary,
        scores: scoresMap,
        narrative: '',
        motion: '',
        recommendations: [],
        llm_model: (resultData as any).llm_model,
        prompt_version: (resultData as any).prompt_version,
      });
      setReportId((resultData as any).report_id ?? null);
      setNarrativeText('');
      setMotionText('');
      setRecommendations([]);
      setStreaming(true);
      setError(null);
      setView('result');

      // Stream the LLM-generated narrative, trait motion, and recommendations.
      try {
        resultStreamRef.current = streamAssessmentResult(
          sessionId!,
          (event) => {
            if (event.type === 'narrative') {
              setNarrativeText((prev) => prev + (event.delta || ''));
            } else if (event.type === 'motion') {
              setMotionText((prev) => prev + (event.delta || ''));
            } else if (event.type === 'recommendations') {
              setRecommendations(Array.isArray(event.recommendations) ? event.recommendations : []);
            }
          },
          () => {
            setStreaming(false);
            // Fallback: pull any recommendations already persisted server-side.
            if (sessionId) {
              getSessionRecommendations(sessionId).then((data: unknown) => {
                const recs = (data as { [key: string]: unknown }).recommendations;
                if (Array.isArray(recs) && recs.length > 0) {
                  setRecommendations(recs);
                }
              }).catch(() => {
                /* recommendations stay empty */
              });
            }
          },
        );
      } catch (err) {
        console.warn('Result stream failed', err);
        setStreaming(false);
        // One-shot fallback when streaming is unavailable.
        fetchAssessmentResult(sessionId!).then((res: AssessmentResult) => {
          setNarrativeText(res.narrative || '');
          setMotionText(res.motion || '');
          if (res.recommendations?.length > 0) {
            setRecommendations(res.recommendations);
          }
        }).catch(() => {
          setStreaming(false);
        });
      }
    } catch (err) {
      console.warn('Backend completeAssessment failed, calculating result locally:', err);
      // Fallback: calculate result from submitted answers so user always sees their result
      const localResult = analyseLocally();
      setResult(localResult);
      setStreaming(false);
      setNarrativeText(localResult.narrative || '');
      setMotionText('');
      setRecommendations([]);
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

  const handleRecFeedback = async (recId: string, status: 'accepted' | 'dismissed' | 'in_progress') => {
    try {
      await submitRecommendationFeedback(recId, { event: 'status_change', status });
      setRecommendations((prev) =>
        prev.map((r) => (r.id === recId ? { ...r, status } : r)),
      );
    } catch (e) {
      console.warn('Recommendation feedback failed', e);
    }
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

        {view === 'intro' && (
          <section id="intro" className="intro">
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
        )}

        {view === 'quiz' && (
          <section id="quiz" className="quiz">
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
        )}

        {view === 'result' && (
          <section id="result" className="result">
            <div className="bar"></div>
            {result ? (
              <>
                <p className="count">Your dominant temperament</p>
                <h2 id="rname">{result.dominant}</h2>
                <p className="lead" id="rsummary">{result.summary ?? ''}</p>

                {streaming && (
                  <div className="stream-status" role="status" aria-live="polite">
                    <span className="stream-dot" aria-hidden="true"></span>
                    <span className="stream-dot" aria-hidden="true"></span>
                    <span className="stream-dot" aria-hidden="true"></span>
                    Agent Bleu is synthesizing your narrative, trait motion, and recommendations…
                  </div>
                )}

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

                {/* Live streamed narrative (Narrative Service) */}
                {(streaming || narrativeText || result.narrative) && (
                  <div className="narrative-card">
                    <div className="narrative-header">
                      <span className="narrative-title">Live Generated Reflective Narrative</span>
                      <span className={`narrative-badge ${streaming ? 'streaming' : ''}`}>
                        {streaming ? 'AI Synthesis • Streaming' : 'AI Synthesis'}
                      </span>
                    </div>
                    <div className="narrative-text">
                      {(narrativeText || result.narrative || '')
                        .split('\n\n')
                        .map((para, i) => (
                          <p key={i}>{para.trim()}</p>
                        ))}
                      {streaming && <span className="stream-cursor" aria-hidden="true">▋</span>}
                    </div>
                    <div className="narrative-meta">
                      Narrative Service • {result.llm_model ? `model: ${result.llm_model}` : 'framework fallback'}
                      • {result.prompt_version || 'v1.0.0'} • Verified Non-Diagnostic
                    </div>
                  </div>
                )}

                {/* Live streamed trait motion (Motion Service) */}
                {(streaming || motionText || result.motion) && (
                  <div className="motion-card">
                    <div className="narrative-header">
                      <span className="narrative-title">Trait Motion — how your tendencies flow</span>
                      <span className={`narrative-badge ${streaming ? 'streaming' : ''}`}>
                        {streaming ? 'AI Synthesis • Streaming' : 'AI Synthesis'}
                      </span>
                    </div>
                    <div className="narrative-text">
                      {(motionText || result.motion || '')
                        .split('\n\n')
                        .map((para, i) => (
                          <p key={i}>{para.trim()}</p>
                        ))}
                      {streaming && <span className="stream-cursor" aria-hidden="true">▋</span>}
                    </div>
                    <div className="narrative-meta">
                      Motion Service • dynamic trait interplay • Verified Non-Diagnostic
                    </div>
                  </div>
                )}

                {/* Recommendations (Recommendation Service) */}
                <section className="recommendations">
                  <h3>Personalized Recommendations</h3>
                  <p className="rec-note">
                    Psychoeducational suggestions matched to your scores and emotion self-reports
                    — not medical or psychiatric advice.
                  </p>
                  {recommendations.length > 0 ? (
                    recommendations.map((rec) => {
                      const body = rec.body;
                      return (
                        <div key={rec.id} className="rec-card">
                          <div className="rec-head">
                            <span className="rec-title">
                              {typeof rec.title === 'string' ? rec.title : String(rec.template_id)}
                            </span>
                            <span className="rec-status">{rec.status}</span>
                          </div>
                          {body ? (
                            <div className="rec-body">
                              {typeof body === 'string' ? (
                                <p>{body}</p>
                              ) : (
                                <>
                                  {body.why && (
                                    <p>
                                      <span className="rec-label">Why it fits:</span> {String(body.why)}
                                    </p>
                                  )}
                                  {body.what && (
                                    <p>
                                      <span className="rec-label">What to try:</span> {String(body.what)}
                                    </p>
                                  )}
                                  {Array.isArray(body.how) && body.how.length > 0 && (
                                    <>
                                      <span className="rec-label">How:</span>
                                      <ul className="rec-how">
                                        {body.how.map((step, i) => (
                                          <li key={i}>{String(step)}</li>
                                        ))}
                                      </ul>
                                    </>
                                  )}
                                  {body.measure && (
                                    <p>
                                      <span className="rec-label">Check:</span> {String(body.measure)}
                                    </p>
                                  )}
                                  {body.professional_support_when && (
                                    <p className="rec-support">
                                      <span className="rec-label">Consider support when:</span>{' '}
                                      {String(body.professional_support_when)}
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          ) : null}
                          <div className="rec-actions">
                            <button
                              className="btn ghost rec-btn"
                              onClick={() => handleRecFeedback(rec.id, 'accepted')}
                            >
                              Mark accepted
                            </button>
                            <button
                              className="btn ghost rec-btn"
                              onClick={() => handleRecFeedback(rec.id, 'dismissed')}
                            >
                              Dismiss
                            </button>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <p className="rec-empty">
                      No recommendations were triggered for this session. Recommendations appear when
                      your scores or emotion self-reports match a care guideline.
                    </p>
                  )}
                </section>

                <div className="result-meta">
                  {reportId && <span>Report {reportId}</span>}
                  {result.llm_model && <span>Model: {result.llm_model}</span>}
                  <span>Synthesized by PsychemetreAI Orchestration Agent • Verified Non-Diagnostic</span>
                </div>
              </>
            ) : null}
            {result && (
              <button className="btn ghost" id="restart" onClick={handleRestart}>
                Retake analysis
              </button>
            )}
          </section>
        )}

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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
