// frontend/src/App.tsx
import React from 'react';
import NowPlaying from './components/NowPlaying';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="App">
      <h1>Discord Music Bot</h1>
      <NowPlaying />
    </div>
  );
};

export default App;