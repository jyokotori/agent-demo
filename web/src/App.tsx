import ChatWidget from './components/ChatWidget';
import './styles/app.css';

function App() {
  return (
    <div className="app-container">
      <main className="app-hero">
        <section className="hero-card">
          <h1 className="hero-title">智能预约助手</h1>
          <p className="hero-subtitle">
            通过对话完成预约，只需告诉我需要的设备和时间。我们的智能体会实时确认资源可用性，
            并在准备就绪时为您呈现确认信息。
          </p>
          <div className="hero-actions">
            <button className="hero-button primary">开始体验</button>
            <button className="hero-button secondary">了解更多</button>
          </div>
        </section>
      </main>
      <footer className="app-footer">© {new Date().getFullYear()} 智能体预约平台</footer>
      <ChatWidget />
    </div>
  );
}

export default App;
