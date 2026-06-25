import { useEffect, useState } from "react";
import "./App.css";

type Stats = {
  total_postcards: number;
  total_origin_countries: number;
  total_receiving_countries: number;
  min_distance: number;
  max_distance: number;
  avg_distance: number;
};

type Postcard = {
  id: string;
  name: string;
  origin_country: string;
  receiving_country: string;
  origin_city: string;
  receiving_city: string;
  distance: number;
  time: number;
  date_sent: string;
  date_received: string;
};

type FilterOptions = {
  origin_countries: string[];
  receiving_countries: string[];
};

function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [postcards, setPostcards] = useState<Postcard[]>([]);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);

  const [selectedOrigin, setSelectedOrigin] = useState("");
  const [selectedReceiving, setSelectedReceiving] = useState("");
  const [searchText, setSearchText] = useState("");
  const [minDistance, setMinDistance] = useState("");
  const [maxDistance, setMaxDistance] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [totalMatches, setTotalMatches] = useState(0);
  const [selectedPostcard, setSelectedPostcard] = useState<Postcard | null>(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/stats")
      .then((res) => res.json())
      .then((data) => setStats(data));

    fetch("http://127.0.0.1:8000/filter-options")
      .then((res) => res.json())
      .then((data) => setFilterOptions(data));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    params.set("limit", "20");

    if (selectedOrigin) params.set("origin_country", selectedOrigin);
    if (selectedReceiving) params.set("receiving_country", selectedReceiving);
    if (searchText.trim()) params.set("search", searchText);
    if (minDistance) params.set("min_distance", minDistance);
    if (maxDistance) params.set("max_distance", maxDistance);
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);

    fetch(`http://127.0.0.1:8000/postcards?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        setPostcards(data.postcards);
        setTotalMatches(data.total_matches);
        setSelectedPostcard(null);
      });
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
  ]);

  function clearFilters() {
    setSelectedOrigin("");
    setSelectedReceiving("");
    setSearchText("");
    setMinDistance("");
    setMaxDistance("");
    setStartDate("");
    setEndDate("");
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Postcard Explorer</h1>
          <p>Visual Analytics of Postcrossing Data</p>
        </div>
      </header>

      <section className="stats-grid">
        <div className="stat-card">
          <span>Total Postcards</span>
          <strong>{stats ? stats.total_postcards : "..."}</strong>
        </div>

        <div className="stat-card">
          <span>Origin Countries</span>
          <strong>{stats ? stats.total_origin_countries : "..."}</strong>
        </div>

        <div className="stat-card">
          <span>Receiving Countries</span>
          <strong>{stats ? stats.total_receiving_countries : "..."}</strong>
        </div>

        <div className="stat-card">
          <span>Average Distance</span>
          <strong>{stats ? `${Math.round(stats.avg_distance)} km` : "..."}</strong>
        </div>
      </section>

      <main className="layout">
        <aside className="sidebar">
          <h2>Filters</h2>

          <label>Search</label>
          <input
            type="text"
            placeholder="Search id, country, city..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />

          <label>Origin country</label>
          <select
            value={selectedOrigin}
            onChange={(e) => setSelectedOrigin(e.target.value)}
          >
            <option value="">All origins</option>
            {filterOptions?.origin_countries.map((country) => (
              <option key={country} value={country}>
                {country}
              </option>
            ))}
          </select>

          <label>Receiving country</label>
          <select
            value={selectedReceiving}
            onChange={(e) => setSelectedReceiving(e.target.value)}
          >
            <option value="">All receiving countries</option>
            {filterOptions?.receiving_countries.map((country) => (
              <option key={country} value={country}>
                {country}
              </option>
            ))}
          </select>

          <label>Distance range km</label>
          <div className="distance-row">
            <input
              type="number"
              placeholder="Min"
              value={minDistance}
              onChange={(e) => setMinDistance(e.target.value)}
            />

            <input
              type="number"
              placeholder="Max"
              value={maxDistance}
              onChange={(e) => setMaxDistance(e.target.value)}
            />
          </div>

          <label>Date sent</label>
          <div className="date-row">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />

            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          <button className="clear-button" onClick={clearFilters}>
            Clear filters
          </button>

          <p className="matches">
            Matches: <strong>{totalMatches}</strong>
          </p>

          {selectedPostcard && (
            <div className="selected-panel">
              <h3>Selected Postcard</h3>
              <p>
                <strong>{selectedPostcard.id}</strong>
              </p>
              <p>
                {selectedPostcard.origin_country} →{" "}
                {selectedPostcard.receiving_country}
              </p>
              <p>
                {selectedPostcard.origin_city} →{" "}
                {selectedPostcard.receiving_city}
              </p>
              <p>Distance: {selectedPostcard.distance} km</p>
              <p>Travel time: {selectedPostcard.time} days</p>
              <p>Sent: {selectedPostcard.date_sent}</p>
              <p>Received: {selectedPostcard.date_received}</p>
            </div>
          )}
        </aside>

        <section className="content">
          <h2>Postcards List</h2>

          <div className="postcard-list">
            {postcards.map((card) => (
              <div
                className={`postcard-card ${
                  selectedPostcard?.id === card.id ? "selected" : ""
                }`}
                key={card.id}
                onClick={() => setSelectedPostcard(card)}
              >
                <h3>{card.id}</h3>
                <p>
                  {card.origin_country} → {card.receiving_country}
                </p>
                <p>
                  {card.origin_city} → {card.receiving_city}
                </p>
                <p>
                  Distance: {card.distance} km | Time: {card.time} days
                </p>
                <small>
                  Sent: {card.date_sent} | Received: {card.date_received}
                </small>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;