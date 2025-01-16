// frontend/src/App.tsx
import React from 'react';
import NowPlaying from './components/NowPlaying';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Discord Music Bot</h1>
      </header>
      <main>
        <NowPlaying />
      </main>
    </div>
  );
};

export default App;