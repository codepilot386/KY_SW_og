import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = '';

const scenarioLabelMap = {
  agency: '기관 사칭',
  acquaintance: '지인 사칭',
  loan: '대출 사기형',
};

function App() {
  const [message, setMessage] = useState('');
  const [choices, setChoices] = useState([]);
  const [answerIndex, setAnswerIndex] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [ttsStyle, setTtsStyle] = useState('neutral');

  const [turn, setTurn] = useState(1);
  const [score, setScore] = useState(0);
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastSelected, setLastSelected] = useState(null);
  const [autoVoice, setAutoVoice] = useState(true);

  const [scenarioType, setScenarioType] = useState(null);

  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [username, setUsername] = useState(localStorage.getItem('username') || '');
  const [loginId, setLoginId] = useState('');
  const [loginPw, setLoginPw] = useState('');
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [pastScores, setPastScores] = useState([]);
  const [answerHistory, setAnswerHistory] = useState([]);
  const [analysisReport, setAnalysisReport] = useState(null);

  const [adminMode, setAdminMode] = useState(false);
  const [adminUsers, setAdminUsers] = useState([]);
  const [adminScores, setAdminScores] = useState([]);
  const [editingUserId, setEditingUserId] = useState(null);
  const [editUsername, setEditUsername] = useState('');
  const [editPassword, setEditPassword] = useState('');

  const audioQueueRef = useRef(Promise.resolve());
  const currentAudioRef = useRef(null);
  const audioCacheRef = useRef(new Map());
  const speechTokenRef = useRef(0);

  useEffect(() => {
    const savedToken = localStorage.getItem('token');

    if (savedToken) {
      loadScores(savedToken);
    }
  }, []);

  const stopAllSpeech = () => {
    speechTokenRef.current += 1;

    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
    }

    audioQueueRef.current = Promise.resolve();
  };

  const loadScores = async (savedToken = token) => {
    if (!savedToken) return;

    try {
      const res = await axios.post(`${API_BASE}/api/scores`, {
        token: savedToken,
      });

      setPastScores(res.data.scores || []);
    } catch (error) {
      console.error('점수 불러오기 실패:', error);
    }
  };

  const loadAdminData = async () => {
    if (!token) return;

    try {
      const usersRes = await axios.post(`${API_BASE}/api/admin/users`, {
        token,
      });

      const scoresRes = await axios.post(`${API_BASE}/api/admin/scores`, {
        token,
      });

      setAdminUsers(usersRes.data.users || []);
      setAdminScores(scoresRes.data.scores || []);
      setAdminMode(true);
      setScenarioType(null);
      setReport(null);
      setEditingUserId(null);
      setEditUsername('');
      setEditPassword('');
    } catch (error) {
      console.error('관리자 데이터 불러오기 실패:', error.response?.data || error);
      alert(error.response?.data?.detail || '관리자 데이터를 불러오지 못했습니다.');
    }
  };

  const startEditUser = (user) => {
    setEditingUserId(user.id);
    setEditUsername(user.username);
    setEditPassword('');
  };

  const cancelEditUser = () => {
    setEditingUserId(null);
    setEditUsername('');
    setEditPassword('');
  };

  const saveEditUser = async () => {
    if (!editingUserId) return;

    const usernameValue = editUsername.trim();
    const passwordValue = editPassword.trim();

    if (!usernameValue) {
      alert('아이디를 입력하세요.');
      return;
    }

    if (passwordValue && passwordValue.length < 4) {
      alert('비밀번호는 4자 이상이어야 합니다.');
      return;
    }

    try {
      await axios.post(`${API_BASE}/api/admin/update-user`, {
        token,
        user_id: editingUserId,
        username: usernameValue,
        password: passwordValue || null,
      });

      alert('사용자 정보가 수정되었습니다.');
      cancelEditUser();
      await loadAdminData();
    } catch (error) {
      console.error('사용자 수정 실패:', error.response?.data || error);
      alert(error.response?.data?.detail || '사용자 수정에 실패했습니다.');
    }
  };

  const deleteUser = async (userId) => {
    const ok = window.confirm(
      '정말 이 사용자를 삭제할까요? 해당 사용자의 훈련 기록도 함께 삭제됩니다.'
    );

    if (!ok) return;

    try {
      await axios.post(`${API_BASE}/api/admin/delete-user`, {
        token,
        user_id: userId,
      });

      alert('사용자가 삭제되었습니다.');
      await loadAdminData();
    } catch (error) {
      console.error('사용자 삭제 실패:', error.response?.data || error);
      alert(error.response?.data?.detail || '사용자 삭제에 실패했습니다.');
    }
  };

  const deleteScore = async (scoreId) => {
    const ok = window.confirm('이 훈련 기록을 삭제할까요?');

    if (!ok) return;

    try {
      await axios.post(`${API_BASE}/api/admin/delete-score`, {
        token,
        score_id: scoreId,
      });

      await loadAdminData();
    } catch (error) {
      console.error('점수 삭제 실패:', error.response?.data || error);
      alert(error.response?.data?.detail || '점수 삭제에 실패했습니다.');
    }
  };

  const handleAuth = async () => {
    const id = loginId.trim();
    const pw = loginPw.trim();

    if (!id || !pw) {
      alert('아이디와 비밀번호를 모두 입력하세요.');
      return;
    }

    if (isRegisterMode && pw.length < 4) {
      alert('회원가입 시 비밀번호는 4자 이상 입력해야 합니다.');
      return;
    }

    try {
      if (isRegisterMode) {
        await axios.post(`${API_BASE}/api/register`, {
          username: id,
          password: pw,
        });

        alert('회원가입이 완료되었습니다. 이제 로그인해주세요.');
        setIsRegisterMode(false);
        setLoginPw('');
        return;
      }

      const res = await axios.post(`${API_BASE}/api/login`, {
        username: id,
        password: pw,
      });

      localStorage.setItem('token', res.data.token);
      localStorage.setItem('username', res.data.username);

      setToken(res.data.token);
      setUsername(res.data.username);
      setLoginId('');
      setLoginPw('');

      await loadScores(res.data.token);
    } catch (error) {
      console.error('인증 오류:', error.response?.data || error);

      const detail = error.response?.data?.detail;

      if (isRegisterMode) {
        alert(
          detail ||
            '회원가입에 실패했습니다. 이미 존재하는 아이디이거나 서버 오류입니다.'
        );
      } else {
        alert(
          detail ||
            '로그인에 실패했습니다. 아이디 또는 비밀번호를 확인하세요.'
        );
      }
    }
  };

  const handleLogout = async () => {
    try {
      if (token) {
        await axios.post(`${API_BASE}/api/logout`, { token });
      }
    } catch (error) {
      console.error('로그아웃 오류:', error);
    }

    localStorage.removeItem('token');
    localStorage.removeItem('username');

    setToken('');
    setUsername('');
    setPastScores([]);
    setAdminMode(false);
    goHome();
  };

  const fetchTtsUrl = async (text, style = 'neutral') => {
    if (!text) return null;

    const cacheKey = `${style}:${text}`;

    if (audioCacheRef.current.has(cacheKey)) {
      return audioCacheRef.current.get(cacheKey);
    }

    const response = await axios.post(
      `${API_BASE}/api/tts`,
      { text, style },
      { responseType: 'blob' }
    );

    const audioBlob = new Blob([response.data], { type: 'audio/mpeg' });
    const audioUrl = URL.createObjectURL(audioBlob);

    audioCacheRef.current.set(cacheKey, audioUrl);

    return audioUrl;
  };

  const playAudioUrl = (audioUrl, tokenValue) => {
    return new Promise((resolve) => {
      if (!audioUrl || tokenValue !== speechTokenRef.current) {
        resolve();
        return;
      }

      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;

      audio.onended = () => {
        currentAudioRef.current = null;
        resolve();
      };

      audio.onerror = () => {
        currentAudioRef.current = null;
        resolve();
      };

      audio.play().catch(() => {
        currentAudioRef.current = null;
        resolve();
      });
    });
  };

  const speakQueued = (text, style = 'neutral') => {
    if (!autoVoice || !text) return Promise.resolve();

    const tokenValue = speechTokenRef.current;

    audioQueueRef.current = audioQueueRef.current.then(async () => {
      if (tokenValue !== speechTokenRef.current) return;

      try {
        const audioUrl = await fetchTtsUrl(text, style);

        if (tokenValue !== speechTokenRef.current) return;

        await playAudioUrl(audioUrl, tokenValue);
      } catch (error) {
        console.error('TTS 재생 실패:', error);
      }
    });

    return audioQueueRef.current;
  };

  const applyScene = (data) => {
    const nextMessage = data.message || '상황을 불러오지 못했습니다.';
    const nextStyle = data.tts_style || 'neutral';

    setMessage(nextMessage);
    setChoices(data.choices || []);
    setAnswerIndex(data.answer_index ?? null);
    setFeedback(data.feedback || '');
    setTtsStyle(nextStyle);
    setLastSelected(null);

    speakQueued(nextMessage, nextStyle);
  };
  const buildAnalysisReport = (finalScore, history, type) => {
  const totalCount = history.length;
  const correctCount = history.filter((item) => item.isCorrect).length;
  const wrongCount = totalCount - correctCount;

  const scenarioName = scenarioLabelMap[type] || '보이스피싱';

  let level = '';
  let summary = '';
  let goodPoints = [];
  let cautionPoints = [];
  let nextTips = [];

  if (finalScore >= 80) {
    level = '안전';
    summary = `${scenarioName} 상황에서 전반적으로 안전한 선택을 잘 했습니다. 특히 급하게 반응하지 않고, 공식 경로로 확인하려는 판단이 좋았습니다.`;
    goodPoints = [
      '낯선 연락에서 바로 개인정보를 제공하지 않는 태도가 좋았습니다.',
      '상대방의 압박이나 급한 분위기에 바로 휘둘리지 않았습니다.',
      '공식 번호, 공식 앱, 기존 연락처 등 안전한 확인 경로를 선택했습니다.',
    ];
    cautionPoints = [
      '실제 상황에서는 목소리나 말투가 더 자연스러울 수 있으니 끝까지 경계해야 합니다.',
      '상대방이 기관명이나 지인 이름을 말하더라도 바로 믿지 않는 습관이 필요합니다.',
    ];
    nextTips = [
      '다음 훈련에서는 더 빠르게 통화를 종료하고 공식 경로로 확인하는 선택을 연습해보세요.',
      '문자 링크, 앱 설치 요구, 인증번호 요구가 나오면 즉시 의심하세요.',
    ];
  } else if (finalScore >= 50) {
    level = '주의';
    summary = `${scenarioName} 상황에서 일부 안전한 선택을 했지만, 아직 상대방의 압박이나 그럴듯한 설명에 흔들릴 가능성이 있습니다.`;
    goodPoints = [
      '일부 상황에서는 개인정보를 보호하려는 선택을 했습니다.',
      '상대방의 말을 무조건 따르지 않으려는 판단이 있었습니다.',
    ];
    cautionPoints = [
      '급하다는 말이나 불이익을 암시하는 말에 반응할 가능성이 있습니다.',
      '상대방이 알려준 번호나 링크를 그대로 믿으면 위험할 수 있습니다.',
      '지인 사칭이나 기관 사칭에서는 반드시 기존 연락처나 공식 대표번호로 다시 확인해야 합니다.',
    ];
    nextTips = [
      '통화 중 조금이라도 이상하면 “제가 직접 확인하겠습니다”라고 말하고 끊는 연습을 해보세요.',
      '상대방이 재촉할수록 더 천천히 판단해야 합니다.',
      '개인정보, 인증번호, 계좌 관련 요청은 무조건 의심하세요.',
    ];
  } else {
    level = '위험';
    summary = `${scenarioName} 상황에서 위험한 선택이 많았습니다. 실제 상황이었다면 개인정보 노출이나 금전 피해로 이어질 가능성이 있습니다.`;
    goodPoints = [
      '훈련을 통해 위험한 상황을 미리 경험했다는 점은 좋습니다.',
      '틀린 선택을 통해 어떤 말투와 상황이 위험한지 확인할 수 있었습니다.',
    ];
    cautionPoints = [
      '상대방이 급하게 행동을 요구할 때 바로 따르는 선택은 매우 위험합니다.',
      '상대방이 알려주는 링크, 번호, 절차를 그대로 따르면 피해로 이어질 수 있습니다.',
      '지인이나 기관을 사칭하는 말에 신원을 확인하지 않고 대응하면 위험합니다.',
      '개인정보, 인증번호, 송금, 앱 설치 요구는 대표적인 보이스피싱 신호입니다.',
    ];
    nextTips = [
      '낯선 연락은 일단 끊고 공식 경로로 직접 확인하는 습관을 먼저 익히세요.',
      '“지금 바로 해야 한다”는 말이 나오면 사기를 의심하세요.',
      '다음 훈련에서는 정답 선택지를 천천히 읽고, 가장 안전한 행동을 고르는 연습을 해보세요.',
    ];
  }

  const wrongFeedbacks = history
    .filter((item) => !item.isCorrect && item.feedback)
    .map((item) => item.feedback);

  return {
    level,
    summary,
    totalCount,
    correctCount,
    wrongCount,
    goodPoints,
    cautionPoints,
    nextTips,
    wrongFeedbacks,
  };
};

  const resetTrainingState = () => {
    setTurn(1);
    setScore(0);
    setReport(null);
    setFeedback('');
    setMessage('');
    setChoices([]);
    setAnswerIndex(null);
    setAnswerHistory([]);
    setAnalysisReport(null);
    setLastSelected(null);
    setTtsStyle('neutral');
  };

  const startTrainingWithType = async (type) => {
    stopAllSpeech();
    resetTrainingState();

    setScenarioType(type);
    setAdminMode(false);
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/start`, {
        scenario_type: type,
      });

      applyScene(response.data);
    } catch (error) {
      console.error(error.response?.data || error);
      alert('서버 오류가 발생했습니다.');
      setScenarioType('select');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChoiceClick = async (choiceText, index) => {
    if (isLoading) return;

    const isCorrect = index === answerIndex;
    const nextScore = score + (isCorrect ? 10 : 0); 
    const currentRecord = {
      turn,
      scenarioType,
      userChoice: choiceText,
      correctAnswer: choices[answerIndex],
      isCorrect,
      feedback,
    };

    setLastSelected(index);

    if (isCorrect) {
      setScore(nextScore);
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, {
        previous_message: message,
        user_response: choiceText,
        turn_count: turn,
        answer_index: answerIndex,
        scenario_type: scenarioType,
      });

      if (response.data.is_finished) {
  const finalHistory = [...answerHistory, currentRecord];

  const finalReport = {
    score: nextScore,
    feedback:
      response.data.report?.feedback ||
      '훈련이 종료되었습니다.',
    tip:
      response.data.report?.tip ||
      '수상한 연락은 끊고 공식 번호로 직접 확인하세요.',
  };

  const generatedAnalysis = buildAnalysisReport(
    nextScore,
    finalHistory,
    scenarioType
  );

  setAnswerHistory(finalHistory);
  setAnalysisReport(generatedAnalysis);
  setReport(finalReport);


        try {
          await axios.post(`${API_BASE}/api/save-score`, {
            token,
            scenario_type: scenarioType,
            score: nextScore,
          });

          await loadScores(token);
        } catch (saveError) {
          console.error('점수 저장 실패:', saveError);
        }

        speakQueued(finalReport.feedback, 'feedback');
      } else {
        setAnswerHistory((prev) => [...prev, currentRecord]);
        setTurn((prev) => prev + 1);
        applyScene(response.data);
      }
    } catch (error) {
      console.error(error.response?.data || error);
      alert('통신 에러가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const goHome = () => {
    stopAllSpeech();
    resetTrainingState();
    setScenarioType(null);
    setAdminMode(false);
    setIsLoading(false);
  };

  const goScenarioSelect = () => {
    stopAllSpeech();
    resetTrainingState();
    setScenarioType('select');
    setAdminMode(false);
    setIsLoading(false);
  };

  if (!token) {
    return (
      <main className="page">
        <section className="login-card">
          <div className="login-header">
            <span className="login-badge">
              {isRegisterMode ? '회원가입' : '로그인'}
            </span>

            <h1>AI 보이스피싱 훈련 플랫폼</h1>

            <p>
              개인별 훈련 점수를 저장하려면 먼저 로그인하거나 회원가입하세요.
            </p>
          </div>

          {isRegisterMode && (
            <div className="notice-box">
              <strong>회원가입 전 확인사항</strong>

              <ul>
                <li>아이디는 로그인할 때 사용됩니다.</li>
                <li>비밀번호는 4자 이상 입력하세요.</li>
                <li>이미 가입된 아이디는 다시 사용할 수 없습니다.</li>
                <li>회원가입 후 로그인 화면에서 다시 로그인해야 합니다.</li>
              </ul>
            </div>
          )}

          {!isRegisterMode && (
            <div className="notice-box small">
              <strong>로그인 안내</strong>

              <p>
                아직 계정이 없다면 아래의 회원가입하기 버튼을 눌러 계정을 먼저 만들어주세요.
              </p>
            </div>
          )}

          <div className="login-form">
            <label>
              아이디

              <input
                type="text"
                placeholder="아이디를 입력하세요"
                value={loginId}
                onChange={(e) => setLoginId(e.target.value)}
              />
            </label>

            <label>
              비밀번호

              <input
                type="password"
                placeholder="비밀번호를 입력하세요"
                value={loginPw}
                onChange={(e) => setLoginPw(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleAuth();
                  }
                }}
              />
            </label>
          </div>

          <button className="login-main-button" onClick={handleAuth}>
            {isRegisterMode ? '회원가입 완료하기' : '로그인하기'}
          </button>

          <button
            className="login-sub-button"
            onClick={() => {
              setIsRegisterMode(!isRegisterMode);
              setLoginPw('');
            }}
          >
            {isRegisterMode
              ? '이미 계정이 있나요? 로그인하기'
              : '계정이 없나요? 회원가입하기'}
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="dashboard">
        <header className="topbar">
          <div className="brand">
            <span className="brand-icon">AI</span>
            <span>AI 기반 보이스피싱 대응 및 훈련 플랫폼</span>
          </div>

          <div className="top-actions">
            <span className="user-name">{username}님</span>

            {username === 'admin' && (
              <button className="home-button admin-button" onClick={loadAdminData}>
                관리자모드
              </button>
            )}

            <button className="home-button" onClick={goHome}>
              홈으로
            </button>

            <button className="home-button" onClick={handleLogout}>
              로그아웃
            </button>
          </div>
        </header>

        {adminMode && (
          <section className="admin-page">
            <div className="admin-header">
              <div>
                <span className="status-badge">관리자모드</span>
                <h1>사용자 및 훈련 기록 관리</h1>
                <p>회원 정보 수정, 비밀번호 재설정, 훈련 기록 삭제가 가능합니다.</p>
              </div>

              <button className="blue-button" onClick={loadAdminData}>
                새로고침
              </button>
            </div>

            <div className="admin-grid">
              <section className="admin-card">
                <h2>회원 목록</h2>

                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>아이디</th>
                        <th>새 비밀번호</th>
                        <th>훈련 수</th>
                        <th>평균 점수</th>
                        <th>가입일</th>
                        <th>관리</th>
                      </tr>
                    </thead>

                    <tbody>
                      {adminUsers.length === 0 ? (
                        <tr>
                          <td colSpan="7">회원 데이터가 없습니다.</td>
                        </tr>
                      ) : (
                        adminUsers.map((user) => (
                          <tr key={user.id}>
                            <td>{user.id}</td>

                            <td>
                              {editingUserId === user.id ? (
                                <input
                                  className="admin-input"
                                  value={editUsername}
                                  onChange={(e) => setEditUsername(e.target.value)}
                                />
                              ) : (
                                user.username
                              )}
                            </td>

                            <td>
                              {editingUserId === user.id ? (
                                <input
                                  className="admin-input"
                                  type="password"
                                  placeholder="변경 시 입력"
                                  value={editPassword}
                                  onChange={(e) => setEditPassword(e.target.value)}
                                />
                              ) : (
                                '-'
                              )}
                            </td>

                            <td>{user.training_count}</td>
                            <td>{user.avg_score}</td>
                            <td>{String(user.created_at).slice(0, 10)}</td>

                            <td>
                              {editingUserId === user.id ? (
                                <div className="admin-actions">
                                  <button onClick={saveEditUser}>저장</button>
                                  <button onClick={cancelEditUser}>취소</button>
                                </div>
                              ) : (
                                <div className="admin-actions">
                                  <button onClick={() => startEditUser(user)}>
                                    수정
                                  </button>

                                  {user.username !== 'admin' && (
                                    <button
                                      className="danger-button"
                                      onClick={() => deleteUser(user.id)}
                                    >
                                      삭제
                                    </button>
                                  )}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="admin-card">
                <h2>최근 훈련 점수</h2>

                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>사용자</th>
                        <th>훈련 유형</th>
                        <th>점수</th>
                        <th>결과</th>
                        <th>날짜</th>
                        <th>관리</th>
                      </tr>
                    </thead>

                    <tbody>
                      {adminScores.length === 0 ? (
                        <tr>
                          <td colSpan="7">훈련 기록이 없습니다.</td>
                        </tr>
                      ) : (
                        adminScores.map((item) => (
                          <tr key={item.id}>
                            <td>{item.id}</td>
                            <td>{item.username}</td>
                            <td>{item.scenario_name}</td>
                            <td>{item.score}점</td>
                            <td>{item.result_label}</td>
                            <td>{String(item.created_at).slice(0, 10)}</td>
                            <td>
                              <button
                                className="danger-button"
                                onClick={() => deleteScore(item.id)}
                              >
                                삭제
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </section>
        )}

        {!adminMode && scenarioType === null && (
          <div className="home-grid">
            <section className="welcome-card">
              <h1>반가워요, 안전한 디지털 환경을 구축합니다.</h1>

              <p>
                본 플랫폼은 실전과 유사한 보이스피싱 시나리오를
                시뮬레이션하여 유저의 취약성을 분석하고 최적의 대처
                가이드를 제공합니다.
              </p>

              <label className="voice-check">
                <input
                  type="checkbox"
                  checked={autoVoice}
                  onChange={(e) => setAutoVoice(e.target.checked)}
                />
                TTS 음성 자동 재생
              </label>

              <button
                className="blue-button"
                onClick={() => setScenarioType('select')}
                disabled={isLoading}
              >
                새로운 훈련 시작하기
              </button>
            </section>

            <section className="score-card">
              <h2>{username}님의 과거 훈련 점수</h2>

              <div className="score-list">
                {pastScores.length === 0 ? (
                  <p className="empty-score">아직 저장된 훈련 점수가 없습니다.</p>
                ) : (
                  pastScores.map((item, index) => (
                    <div className="score-row" key={index}>
                      <span>{item.scenario_name}</span>

                      <strong
                        className={
                          item.result_label === '안전'
                            ? 'safe'
                            : item.result_label === '위험'
                              ? 'danger'
                              : 'warning'
                        }
                      >
                        {item.score}점 ({item.result_label})
                      </strong>
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>
        )}

        {!adminMode && scenarioType === 'select' && (
          <div className="scenario-select">
            <span className="status-badge">훈련 유형 선택</span>

            <h1>어떤 유형의 보이스피싱을 훈련할까요?</h1>

            <p className="scenario-desc">
              실제 상황처럼 진행될 훈련 유형을 선택하세요.
            </p>

            <div className="scenario-buttons">
              <button onClick={() => startTrainingWithType('agency')}>
                <strong>기관 사칭</strong>
                <span>검찰, 경찰, 금융기관을 사칭하는 연락 대응 훈련</span>
              </button>

              <button onClick={() => startTrainingWithType('acquaintance')}>
                <strong>지인 사칭</strong>
                <span>가족, 친구, 지인을 사칭한 메신저·전화 대응 훈련</span>
              </button>

              <button onClick={() => startTrainingWithType('loan')}>
                <strong>대출 사기형</strong>
                <span>저금리 대출, 승인 안내, 수수료 요구 대응 훈련</span>
              </button>
            </div>

            <button className="back-btn" onClick={goHome}>
              홈으로 돌아가기
            </button>
          </div>
        )}

        {!adminMode && scenarioType !== null && scenarioType !== 'select' && report && (
  <section className="result-card">
    <span className="status-badge">훈련 종료</span>

    <h1>{report.score}점</h1>

    <p>{report.feedback}</p>

    {analysisReport && (
      <div className="analysis-box">
        <h2>훈련 분석 결과</h2>

        <div className="analysis-summary">
          <strong>판정: {analysisReport.level}</strong>
          <p>{analysisReport.summary}</p>
          <span>
            총 {analysisReport.totalCount}문항 중 정답 {analysisReport.correctCount}개,
            주의 필요 선택 {analysisReport.wrongCount}개
          </span>
        </div>

        <div className="analysis-section">
          <h3>잘한 점</h3>
          <ul>
            {analysisReport.goodPoints.map((item, index) => (
              <li key={`good-${index}`}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="analysis-section warning-section">
          <h3>조심해야 할 점</h3>
          <ul>
            {analysisReport.cautionPoints.map((item, index) => (
              <li key={`caution-${index}`}>{item}</li>
            ))}
          </ul>
        </div>

        {analysisReport.wrongFeedbacks.length > 0 && (
          <div className="analysis-section">
            <h3>틀린 선택에서 나온 핵심 피드백</h3>
            <ul>
              {analysisReport.wrongFeedbacks.map((item, index) => (
                <li key={`wrong-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="analysis-section">
          <h3>다음 훈련 팁</h3>
          <ul>
            {analysisReport.nextTips.map((item, index) => (
              <li key={`tip-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    )}

    <div className="tip-box">
      <strong>안전 팁</strong>
      <span>{report.tip}</span>
    </div>

    <button className="blue-button" onClick={goScenarioSelect}>
      다른 훈련 다시하기
    </button>
  </section>
)}

        {!adminMode && scenarioType !== null && scenarioType !== 'select' && !report && (
          <section className="training-layout">
            <div className="training-card">
              <div className="training-header">
                <div>
                  <span className="status-badge">
                    {scenarioLabelMap[scenarioType]} 훈련
                  </span>

                  <h1>낯선 번호 · 통화 중</h1>
                </div>

                <div className="turn-box">
                  <span>진행도</span>
                  <strong>{turn}/10</strong>
                </div>
              </div>

              <div className="progress">
                <div
                  className="progress-fill"
                  style={{ width: `${Math.min(turn * 10, 100)}%` }}
                />
              </div>

              <div className="call-box">
                <span className="call-label">상대방 음성</span>

                <p>
                  {isLoading && !message
                    ? '첫 통화를 연결하는 중...'
                    : isLoading
                      ? '다음 통화를 연결하는 중...'
                      : message}
                </p>

                {message && (
                  <button
                    className="listen-button"
                    onClick={() => speakQueued(message, ttsStyle)}
                  >
                    다시 듣기
                  </button>
                )}
              </div>

              {lastSelected !== null && (
                <div
                  className={
                    lastSelected === answerIndex
                      ? 'feedback-box good'
                      : 'feedback-box bad'
                  }
                >
                  <strong>
                    {lastSelected === answerIndex
                      ? '정답입니다.'
                      : '주의가 필요합니다.'}
                  </strong>

                  <span>{feedback}</span>
                </div>
              )}

              <div className="choice-list">
                {choices.map((choice, index) => (
                  <button
                    key={`${choice}-${index}`}
                    className="choice-button"
                    onClick={() => handleChoiceClick(choice, index)}
                    disabled={isLoading}
                  >
                    {choice}
                  </button>
                ))}
              </div>
            </div>

            <aside className="side-panel">
              <h2>현재 훈련 상태</h2>

              <div className="info-row">
                <span>훈련 유형</span>
                <strong>{scenarioLabelMap[scenarioType]}</strong>
              </div>

              <div className="info-row">
                <span>현재 점수</span>
                <strong>{score}점</strong>
              </div>

              <div className="info-row">
                <span>자동 음성</span>
                <strong>{autoVoice ? 'ON' : 'OFF'}</strong>
              </div>

              <div className="info-row">
                <span>음성 스타일</span>
                <strong>{ttsStyle}</strong>
              </div>

              <p className="guide-text">
                낯선 연락에서 개인정보, 인증번호, 송금 요구가 나오면
                통화를 종료하고 공식 번호로 직접 확인하세요.
              </p>
            </aside>
          </section>
        )}
      </section>
    </main>
  );
}

export default App;