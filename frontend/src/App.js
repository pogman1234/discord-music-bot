// frontend/src/App.js
import React from 'react';
import NowPlaying from './components/NowPlaying';
import './App.css'; // If you have any CSS

const App = () => {
  return (
    <div className="App">
      <h1>Discord Music Bot</h1>
      <NowPlaying />
      {/* Other components can be added here later */}
    </div>
  );
};

export default App;