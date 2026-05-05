"use client";

import { useState, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';

// Use environment variable for production, fallback to dynamic hostname for local dev
const getApiBase = () => {
  // Check for production environment variable first
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  // Fallback for local development - use current hostname
  if (typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000';
};
const API_BASE = getApiBase();

interface Question {
  id: string;
  text: string;
  type: 'boolean' | 'choice' | 'number' | 'text';
  options?: string[];
}

interface Progress {
  current: number;
  estimated_total: number;
}

interface Message {
  id: string;
  text: string;
  sender: 'ai' | 'user';
  type?: 'question' | 'result' | 'emergency' | 'empathy';
  data?: any;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [canGoBack, setCanGoBack] = useState(false);
  const [tempUnit, setTempUnit] = useState<'C' | 'F'>('C');
  const [inputError, setInputError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const resetSession = () => {
    setMessages([]);
    setSessionId(null);
    setCurrentQuestion(null);
    setProgress(null);
    setInputValue("");
    setCanGoBack(false);
    setInputError(null);
  };

  const startSession = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/session/start`, { method: 'POST' });
      const data = await res.json();
      setSessionId(data.session_id);
      setCurrentQuestion(data.next_question);
      setProgress({ current: 1, estimated_total: 12 });
      setMessages([
        {
          id: uuidv4(),
          text: data.message,
          sender: 'ai'
        },
        {
          id: uuidv4(),
          text: data.next_question.text,
          sender: 'ai',
          type: 'question'
        }
      ]);
    } catch (err) {
      console.error(err);
      setMessages([{ id: uuidv4(), text: "Failed to connect to backend. Please ensure it's running.", sender: 'ai' }]);
    }
    setLoading(false);
  };

  const goBack = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/session/undo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      const data = await res.json();

      // Remove last two messages (user answer + question)
      setMessages(prev => prev.slice(0, -2));

      if (data.next_question) {
        setCurrentQuestion(data.next_question);
        setMessages(prev => [...prev, {
          id: uuidv4(),
          text: data.next_question.text,
          sender: 'ai',
          type: 'question'
        }]);
      }
      if (data.progress) {
        setProgress(data.progress);
      }
      setCanGoBack(data.can_go_back);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const validateTemperature = (value: number): boolean => {
    if (tempUnit === 'C') {
      if (value < 35 || value > 42) {
        setInputError("Temperature should be between 35°C and 42°C");
        return false;
      }
    } else {
      if (value < 95 || value > 107.6) {
        setInputError("Temperature should be between 95°F and 107.6°F");
        return false;
      }
    }
    setInputError(null);
    return true;
  };

  const convertToCelsius = (fahrenheit: number): number => {
    return Math.round(((fahrenheit - 32) * 5 / 9) * 10) / 10;
  };

  const submitAnswer = async (answer: any, label: string) => {
    if (!sessionId || !currentQuestion) return;

    // Validate temperature if applicable
    if (currentQuestion.id === 'temperature' && currentQuestion.type === 'number') {
      const numValue = Number(answer);
      if (!validateTemperature(numValue)) return;
      // Convert to Celsius if needed
      if (tempUnit === 'F') {
        answer = convertToCelsius(numValue);
        label = `${numValue}°F (${answer}°C)`;
      }
    }

    setMessages(prev => [...prev, { id: uuidv4(), text: label, sender: 'user' }]);
    setInputValue("");
    setInputError(null);

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/session/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          question_id: currentQuestion.id,
          answer: answer
        })
      });
      const data = await res.json();

      if (data.progress) setProgress(data.progress);
      if (data.can_go_back !== undefined) setCanGoBack(data.can_go_back);

      // Add empathy message if present
      if (data.empathy_message) {
        setMessages(prev => [...prev, {
          id: uuidv4(),
          text: data.empathy_message,
          sender: 'ai',
          type: 'empathy'
        }]);
      }

      if (data.emergency) {
        setMessages(prev => [...prev, {
          id: uuidv4(),
          text: data.message,
          sender: 'ai',
          type: 'emergency'
        }]);
        setCurrentQuestion(null);
        setProgress(null);
      } else if (data.next_question) {
        setCurrentQuestion(data.next_question);
        setMessages(prev => [...prev, {
          id: uuidv4(),
          text: data.next_question.text,
          sender: 'ai',
          type: 'question'
        }]);
      } else if (data.message) {
        setMessages(prev => [...prev, {
          id: uuidv4(),
          text: data.message,
          sender: 'ai'
        }]);
        // Auto-trigger to RESULT
        const res2 = await fetch(`${API_BASE}/session/answer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            question_id: 'continue',
            answer: true
          })
        });
        const data2 = await res2.json();
        if (data2.result) {
          setMessages(prev => [...prev, {
            id: uuidv4(),
            text: data2.result.summary,
            sender: 'ai',
            type: 'result',
            data: data2.result
          }]);
        }
        setCurrentQuestion(null);
        setProgress(null);
      } else if (data.result) {
        setMessages(prev => [...prev, {
          id: uuidv4(),
          text: data.result.summary,
          sender: 'ai',
          type: 'result',
          data: data.result
        }]);
        setCurrentQuestion(null);
        setProgress(null);
      }
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'HIGH': return 'text-red-600 bg-red-50 border-red-200';
      case 'MODERATE': return 'text-amber-600 bg-amber-50 border-amber-200';
      default: return 'text-green-600 bg-green-50 border-green-200';
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-2 sm:p-4 md:p-12 bg-slate-50">
      <div className="z-10 w-full max-w-2xl flex items-center justify-center mb-6">
        <h1 className="text-xl font-bold text-blue-800 tracking-tight">AI Doctor</h1>
      </div>

      {/* Progress Indicator */}
      {progress && currentQuestion && (
        <div className="w-full max-w-2xl mb-4">
          <div className="flex items-center justify-between text-sm text-slate-500 mb-2">
            <span className="font-medium">Assessment Progress</span>
            <span className="text-xs">Step {progress.current} of ~{progress.estimated_total}</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-500 h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.min(100, (progress.current / progress.estimated_total) * 100)}%` }}
            ></div>
          </div>
        </div>
      )}

      <div className="flex-1 w-full max-w-2xl bg-white rounded-2xl sm:rounded-[2rem] shadow-2xl shadow-blue-100/50 overflow-hidden flex flex-col border border-slate-100">
        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-6 py-12">
              <div className="w-20 h-20 bg-blue-50 rounded-3xl flex items-center justify-center border border-blue-100">
                <svg className="w-10 h-10 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <div className="text-center space-y-2">
                <h3 className="text-slate-800 font-bold text-xl">Start Your Assessment</h3>
                <p className="max-w-[280px] text-sm text-slate-500">I'll guide you through a series of questions to understand your health concerns.</p>
              </div>
              <button
                onClick={startSession}
                className="px-10 py-4 bg-blue-600 text-white rounded-2xl font-bold hover:bg-blue-700 transition-all shadow-xl shadow-blue-200 active:scale-95"
              >
                Begin Assessment
              </button>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`fade-in flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div className={`chat-bubble ${msg.sender === 'user' ? 'chat-bubble-user' :
                msg.type === 'emergency' ? 'bg-red-50 border-red-100 text-red-900 border-2' :
                  msg.type === 'empathy' ? 'bg-blue-50/50 border-blue-100 text-blue-800 italic text-sm' :
                    'chat-bubble-ai'
                }`}>
                {msg.type === 'emergency' && (
                  <div className="flex items-center mb-3 font-bold text-red-600 text-lg">
                    <svg className="w-6 h-6 mr-2 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    URGENT ACTION REQUIRED
                  </div>
                )}
                <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>

                {msg.type === 'result' && msg.data && (
                  <div className="mt-6 pt-6 border-t border-slate-100 space-y-6">
                    {/* Urgency & Confidence Badges */}
                    <div className="flex gap-2 flex-wrap">
                      {msg.data.urgency && (
                        <div className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${getUrgencyColor(msg.data.urgency)}`}>
                          {msg.data.urgency === 'HIGH' && '⚠️ '}
                          {msg.data.urgency} Priority
                        </div>
                      )}
                      {msg.data.confidence && (
                        <div className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${msg.data.confidence === 'HIGH' ? 'text-blue-600 bg-blue-50 border-blue-200' :
                          msg.data.confidence === 'MEDIUM' ? 'text-slate-600 bg-slate-50 border-slate-200' :
                            'text-orange-600 bg-orange-50 border-orange-200'
                          }`}>
                          {msg.data.confidence === 'LOW' && '❓ '}
                          {msg.data.confidence} Confidence
                        </div>
                      )}
                    </div>

                    {/* Low Confidence Warning */}
                    {msg.data.confidence === 'LOW' && (
                      <div className="bg-orange-50 p-3 rounded-xl border border-orange-100 text-sm text-orange-800">
                        Results are less certain due to symptom overlap. Consider providing more details or consulting a doctor.
                      </div>
                    )}

                    {/* Reported Symptoms Summary */}
                    {msg.data.reported_symptoms && msg.data.reported_symptoms.length > 0 && (
                      <div className="bg-slate-50 p-4 rounded-xl">
                        <h4 className="text-xs font-bold text-slate-600 uppercase tracking-widest mb-2">Symptoms You Reported</h4>
                        <div className="flex flex-wrap gap-2">
                          {msg.data.reported_symptoms.map((sym: string) => (
                            <span key={sym} className="px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs text-slate-700">
                              {sym}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Matched Combinations */}
                    {msg.data.matched_combinations && msg.data.matched_combinations.length > 0 && (
                      <div className="bg-purple-50/50 p-4 rounded-xl border border-purple-100">
                        <h4 className="text-xs font-bold text-purple-800 uppercase tracking-widest mb-2">🔗 Matched Symptom Patterns</h4>
                        <div className="flex flex-wrap gap-2">
                          {msg.data.matched_combinations.map((combo: string, i: number) => (
                            <span key={i} className="px-2 py-1 bg-white border border-purple-200 rounded-lg text-xs text-purple-700">
                              {combo}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Probabilistic Assessment */}
                    <div>
                      <h4 className="font-bold text-slate-800 mb-4 flex items-center">
                        <span className="w-2 h-6 bg-blue-500 rounded-full mr-3"></span>
                        Probabilistic Assessment
                      </h4>
                      <div className="space-y-4">
                        {Object.entries(msg.data.probabilities).map(([name, prob]: [string, any]) => (
                          <div key={name}>
                            <div className="flex justify-between items-center text-sm mb-2">
                              <span className="font-semibold text-slate-700">{name}</span>
                              <span className="text-slate-400 font-mono text-xs">{Math.round(prob * 100)}%</span>
                            </div>
                            <div className="w-full bg-slate-50 rounded-full h-2.5 overflow-hidden">
                              <div
                                className="bg-blue-600 h-full rounded-full transition-all duration-1000 ease-out"
                                style={{ width: `${prob * 100}%` }}
                              ></div>
                            </div>
                            {/* Symptom Mapping */}
                            {msg.data.symptom_mapping && msg.data.symptom_mapping[name] && (
                              <p className="text-xs text-slate-500 mt-1 ml-1">
                                Matching: {msg.data.symptom_mapping[name].join(", ")}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Recommendation */}
                    {msg.data.recommendation && (
                      <div className="bg-blue-50/50 p-4 rounded-2xl border border-blue-100/50">
                        <h4 className="text-xs font-bold text-blue-800 uppercase tracking-widest mb-1">Recommendation</h4>
                        <p className="text-sm text-slate-700 leading-relaxed font-medium">{msg.data.recommendation}</p>
                      </div>
                    )}

                    {/* Warning Signs */}
                    {msg.data.warning_signs && msg.data.warning_signs.length > 0 && (
                      <div className="bg-amber-50/50 p-4 rounded-2xl border border-amber-100">
                        <h4 className="text-xs font-bold text-amber-800 uppercase tracking-widest mb-2">⚠️ Return Immediately If You Experience</h4>
                        <ul className="text-sm text-amber-900 space-y-1">
                          {msg.data.warning_signs.slice(0, 4).map((sign: string, i: number) => (
                            <li key={i} className="flex items-start">
                              <span className="mr-2">•</span>
                              {sign}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Recommended Tests */}
                    {msg.data.recommended_tests && msg.data.recommended_tests.length > 0 && (
                      <div className="bg-green-50/50 p-4 rounded-2xl border border-green-100">
                        <h4 className="text-xs font-bold text-green-800 uppercase tracking-widest mb-2">🔬 Suggested Tests</h4>
                        <ul className="text-sm text-green-900 space-y-1">
                          {msg.data.recommended_tests.map((test: string, i: number) => (
                            <li key={i} className="flex items-start">
                              <span className="mr-2">•</span>
                              {test}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Disclaimer */}
                    <p className="text-[10px] text-slate-400 italic bg-slate-50 p-3 rounded-lg border border-slate-100">
                      {msg.data.disclaimer}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-6 md:p-8 border-t border-slate-50 bg-white">
          {/* Go Back Button */}
          {canGoBack && currentQuestion && !loading && (
            <button
              onClick={goBack}
              className="mb-4 text-sm text-slate-500 hover:text-blue-600 flex items-center gap-1 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
              </svg>
              Go back to previous question
            </button>
          )}

          {currentQuestion && !loading && (
            <div className="w-full">
              {currentQuestion.type === 'boolean' && (
                <div className="flex gap-3 justify-center flex-wrap">
                  <button
                    onClick={() => submitAnswer(true, "Yes")}
                    className="flex-1 max-w-[120px] py-4 bg-white border-2 border-slate-100 rounded-2xl font-bold text-slate-700 hover:border-blue-500 hover:text-blue-600 transition-all shadow-sm active:scale-95"
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => submitAnswer(false, "No")}
                    className="flex-1 max-w-[120px] py-4 bg-white border-2 border-slate-100 rounded-2xl font-bold text-slate-700 hover:border-blue-500 hover:text-blue-600 transition-all shadow-sm active:scale-95"
                  >
                    No
                  </button>
                  <button
                    onClick={() => submitAnswer("unknown", "I don't know")}
                    className="px-4 py-4 bg-slate-50 border-2 border-slate-100 rounded-2xl font-medium text-slate-500 hover:border-slate-300 hover:text-slate-600 transition-all text-sm active:scale-95"
                  >
                    I don't know
                  </button>
                </div>
              )}

              {(currentQuestion.type === 'text' || currentQuestion.type === 'number') && (
                <div className="space-y-2">
                  {/* Temperature unit toggle */}
                  {currentQuestion.id === 'temperature' && (
                    <div className="flex justify-center gap-2 mb-2">
                      <button
                        onClick={() => setTempUnit('C')}
                        className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${tempUnit === 'C' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}
                      >
                        °C
                      </button>
                      <button
                        onClick={() => setTempUnit('F')}
                        className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${tempUnit === 'F' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}
                      >
                        °F
                      </button>
                      <button
                        onClick={() => submitAnswer("unknown", "I haven't checked")}
                        className="px-3 py-1 bg-slate-50 rounded-lg text-sm text-slate-500 hover:text-slate-700"
                      >
                        Skip
                      </button>
                    </div>
                  )}
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (inputValue.trim()) {
                        const value = currentQuestion.type === 'number' ? Number(inputValue) : inputValue;
                        const label = currentQuestion.id === 'temperature' ? `${inputValue}°${tempUnit}` : inputValue;
                        submitAnswer(value, label);
                      }
                    }}
                    className="flex flex-col sm:flex-row gap-3"
                  >
                    <input
                      autoFocus
                      type={currentQuestion.type === 'number' ? 'number' : 'text'}
                      step={currentQuestion.type === 'number' ? '0.1' : undefined}
                      value={inputValue}
                      onChange={(e) => {
                        setInputValue(e.target.value);
                        setInputError(null);
                      }}
                      placeholder={currentQuestion.id === 'temperature' ? `Enter temperature in °${tempUnit}` : "Type your response..."}
                      className={`w-full sm:flex-1 px-4 sm:px-6 py-4 bg-slate-50 border-2 ${inputError ? 'border-red-300' : 'border-transparent'} focus:border-blue-200 focus:bg-white rounded-2xl outline-none transition-all text-slate-700 font-medium text-base`}
                    />
                    <button
                      type="submit"
                      className="w-full sm:w-auto px-6 py-4 bg-blue-600 text-white rounded-2xl hover:bg-blue-700 transition-colors shadow-lg shadow-blue-100 font-bold flex items-center justify-center gap-2"
                    >
                      <span className="sm:hidden">Submit</span>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </button>
                  </form>
                  {inputError && (
                    <p className="text-red-500 text-sm text-center">{inputError}</p>
                  )}
                </div>
              )}

              {currentQuestion.type === 'choice' && currentQuestion.options && (
                <div className="flex flex-wrap gap-2 justify-center">
                  {currentQuestion.options.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => submitAnswer(opt, opt)}
                      className="px-6 py-3 bg-white border-2 border-slate-100 rounded-xl font-bold text-slate-600 hover:border-blue-500 hover:text-blue-600 transition-all shadow-sm active:scale-95"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center gap-2 py-4">
              <div className="flex space-x-2">
                <div className="w-2.5 h-2.5 bg-blue-300 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-2.5 h-2.5 bg-blue-300 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-2.5 h-2.5 bg-blue-300 rounded-full animate-bounce"></div>
              </div>
              <p className="text-xs text-slate-400">Analyzing your symptoms...</p>
            </div>
          )}

          {!currentQuestion && !loading && messages.length > 0 && (
            <div className="flex flex-col items-center gap-4">
              <p className="italic text-slate-400 text-xs">Assessment completed.</p>
              <button
                onClick={resetSession}
                className="px-8 py-3 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-700 transition-all shadow-lg shadow-blue-100 active:scale-95"
              >
                Start New Assessment
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Footer with branding */}
      <div className="mt-8 flex flex-col items-center gap-4 pb-4">
        <img src="/crystalHeights.jpeg" alt="Crystal Heights Logo" className="h-16 sm:h-20 object-contain" />
        <p className="text-slate-400 text-xs uppercase tracking-[0.15em] font-medium text-center">
          Made by Crystal Heights International School
        </p>
      </div>
    </main>
  );
}
