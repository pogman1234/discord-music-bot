// frontend/src/components/NowPlaying.js
import React, { useState, useEffect } from 'react';

const NowPlaying = () => {
  const [nowPlaying, setNowPlaying] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/nowplaying');
        const data = await response.json();

        if (response.ok) {
          setNowPlaying(data.title); // Assuming the API returns { "title": "..." }
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

    // Fetch data immediately on component mount
    fetchData();

    // Set up polling (fetch data every 5 seconds)
    const intervalId = setInterval(fetchData, 5000);

    // Clean up interval on component unmount
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