import React, { useState, useEffect } from 'react';

interface NowPlayingProps {}

const NowPlaying: React.FC<NowPlayingProps> = () => {
  const [nowPlaying, setNowPlaying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/nowplaying'); // This is the critical part
        const data = await response.json();

        if (response.ok) {
          setNowPlaying(data.title);
          setError(null);
        } else {
          setError(data.message || 'Error fetching now playing');
          setNowPlaying(null);
        }
      } catch (err) {
        setError('Network error');
        setNowPlaying(null);
      }
    };

    fetchData();
    const intervalId = setInterval(fetchData, 5000);

    return () => clearInterval(intervalId);
  }, []);

  return (
    <div>
      <h2>Now Playing:</h2>
      {nowPlaying ? (
        <p>{nowPlaying}</p>
      ) : error ? (
        <p>Error: {error}</p>
      ) : (
        <p>Loading...</p>
      )}
    </div>
  );
};

export default NowPlaying;