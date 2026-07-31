import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";
const SEMANTIC_CARD_PAGE_SIZE = 120;

const TOPIC_HIERARCHY = [
  {
    id: "nature_scenic",
    label: "Nature & Scenic",
    description: "Coasts, wildlife, landscapes, and scenic postcards",
    clusterIds: [2, 5, 8, 11],
    color: "#0ea5e9",
    x: 30,
    y: 36,
  },
  {
    id: "architecture_heritage",
    label: "Architecture",
    description: "Buildings, monuments, heritage sites, and landmarks",
    clusterIds: [4, 9],
    color: "#2563eb",
    x: 70,
    y: 34,
  },
  {
    id: "graphics_illustrations",
    label: "Graphics & Maps",
    description: "Illustrations, maps, posters, flags, and symbols",
    clusterIds: [1, 7, 10],
    color: "#db2777",
    x: 35,
    y: 73,
  },
  {
    id: "mixed_travel_dark_warm",
    label: "Mixed Travel",
    description: "Warm scenes, night views, travel, and cultural postcards",
    clusterIds: [0, 3, 6],
    color: "#f97316",
    x: 76,
    y: 71,
  },
];

const CLUSTER_SEMANTIC_POSITIONS: Record<number, { x: number; y: number }> = {
  0: { x: 66, y: 31 },
  1: { x: 24, y: 34 },
  2: { x: 20, y: 51 },
  3: { x: 75, y: 74 },
  4: { x: 77, y: 43 },
  5: { x: 31, y: 70 },
  6: { x: 34, y: 27 },
  7: { x: 39, y: 49 },
  8: { x: 83, y: 30 },
  9: { x: 18, y: 67 },
  10: { x: 48, y: 76 },
  11: { x: 85, y: 67 },
};

type MapLevel = "topics" | "clusters" | "pairs" | "cards";

type Stats = {
  total_postcards: number;
  total_origin_countries: number;
  total_receiving_countries: number;
  min_distance: number;
  max_distance: number;
  avg_distance: number;
};

type FilterOptions = {
  origin_countries: string[];
  receiving_countries: string[];
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
  cluster?: number;
  cluster_name?: string;
  cluster_color?: string;
  topic_group_id?: string;
  topic_group_name?: string;
  topic_group_color?: string;
  image_url?: string;
};

type DrilldownNode = {
  id: string;
  type: "topic" | "cluster";
  label: string;
  description?: string;
  color: string;
  count: number;
  lat: number;
  lon: number;
  cluster?: number;
  clusterIds?: number[];
  topic_group_id?: string;
  topic_group_name?: string;
  samples?: Array<{
    id: string;
    name?: string;
    image_url?: string;
  }>;
};

type DrilldownFlow = {
  id: string;
  route_count: number;
  avg_distance: number;
  avg_time: number;
  origin_country: string;
  receiving_country: string;
  origin_iso: string;
  receiving_iso: string;
  origin_lat: number;
  origin_lon: number;
  receiving_lat: number;
  receiving_lon: number;
  cluster: number;
  cluster_name: string;
  cluster_color: string;
  topic_group_id: string;
  topic_group_name: string;
  topic_group_color: string;
};

type DrilldownCard = Postcard & {
  origin_iso: string;
  receiving_iso: string;
  origin_lat: number;
  origin_lon: number;
  receiving_lat: number;
  receiving_lon: number;
  cluster: number;
  cluster_name: string;
  cluster_color: string;
  topic_group_id: string;
  topic_group_name: string;
  topic_group_color: string;
};

type MapDrilldownResponse = {
  level: MapLevel;
  total_cards: number;
  breadcrumb: Array<{
    level: MapLevel;
    label: string;
  }>;
  nodes: DrilldownNode[];
  flows: DrilldownFlow[];
  cards: DrilldownCard[];
};

type SelectedPair = {
  origin_iso: string;
  receiving_iso: string;
  origin_country: string;
  receiving_country: string;
};

type OutlierPostcard = Postcard & {
  distance_z: number;
  time_z: number;
  outlier_score: number;
  outlier_reason: string;
};

type JourneyRoute = DrilldownCard & {
  progress: number;
};

type JourneyFrame = {
  period: string;
  start_date: string;
  end_date: string;
  active_count: number;
  sent_count: number;
  received_count: number;
  shown_routes: number;
  routes: JourneyRoute[];
};

type JourneyAnimationResponse = {
  period: "month" | "year";
  total_cards: number;
  frame_count: number;
  max_active: number;
  routes_per_frame: number;
  frames: JourneyFrame[];
};


// === E6 TOPIC EVOLUTION FRONTEND START ===
type TopicEvolutionValue = {
  period: string;
  count: number;
  country_a_count: number;
  country_b_count: number;
};

type TopicEvolutionSeries = {
  id: string;
  label: string;
  color: string;
  total: number;
  values: TopicEvolutionValue[];
};

type TopicEvolutionResponse = {
  period: "month" | "year";
  abstraction: "topic" | "cluster";
  country_role: "origin" | "receiving";
  country_a: string;
  country_b: string;
  periods: string[];
  series: TopicEvolutionSeries[];
  total_cards: number;
};

type StreamPoint = {
  x: number;
  y0: number;
  y1: number;
  count: number;
  period: string;
};

function buildStreamAreaPath(points: StreamPoint[]) {
  if (points.length === 0) return "";

  const upper = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y0}`).join(" ");
  const lower = [...points].reverse().map((point) => `L ${point.x} ${point.y1}`).join(" ");

  return `${upper} ${lower} Z`;
}

function buildEvolutionChart(data: TopicEvolutionResponse | null) {
  const width = 820;
  const height = 250;
  const left = 42;
  const right = 18;
  const top = 20;
  const bottom = 36;

  const periods = data?.periods ?? [];
  const series = (data?.series ?? []).slice(0, 8);

  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;

  const totals = periods.map((period) =>
    series.reduce((sum, item) => {
      const value = item.values.find((entry) => entry.period === period);
      return sum + (value?.count ?? 0);
    }, 0)
  );

  const maxTotal = Math.max(1, ...totals);
  const stacks = periods.map((_, index) => {
    const totalHeight = (totals[index] / maxTotal) * innerHeight * 0.86;
    const base = top + (innerHeight - totalHeight) / 2;
    return { cursor: base };
  });

  const xFor = (index: number) =>
    periods.length <= 1
      ? left + innerWidth / 2
      : left + (index * innerWidth) / Math.max(1, periods.length - 1);

  const layers = series.map((item) => {
    const points = periods.map((period, index) => {
      const value = item.values.find((entry) => entry.period === period);
      const count = value?.count ?? 0;
      const layerHeight = (count / maxTotal) * innerHeight * 0.86;
      const y0 = stacks[index].cursor;
      const y1 = y0 + layerHeight;
      stacks[index].cursor = y1;

      return {
        x: xFor(index),
        y0,
        y1,
        count,
        period,
      };
    });

    return {
      ...item,
      points,
      path: buildStreamAreaPath(points),
    };
  });

  const countryATotal = series.reduce(
    (sum, item) => sum + item.values.reduce((s, value) => s + value.country_a_count, 0),
    0
  );

  const countryBTotal = series.reduce(
    (sum, item) => sum + item.values.reduce((s, value) => s + value.country_b_count, 0),
    0
  );

  return {
    width,
    height,
    periods,
    layers,
    maxTotal,
    countryATotal,
    countryBTotal,
  };
}
// === E6 TOPIC EVOLUTION FRONTEND END ===

function compactNumber(value: number | undefined | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return "0";

  return new Intl.NumberFormat("en", {
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: value >= 10000 ? 1 : 0,
  }).format(value);
}

function mapNodeRadius(count: number) {
  return Math.max(18, Math.min(56, 16 + Math.sqrt(Math.max(1, count)) * 0.42));
}

function clusterNodeRadius(count: number) {
  return Math.max(13, Math.min(40, 12 + Math.sqrt(Math.max(1, count)) * 0.34));
}

function lineWeight(count: number) {
  return Math.max(2, Math.min(9, 1.5 + Math.sqrt(Math.max(1, count)) * 0.32));
}

function semanticSize(count: number, min = 96, max = 196) {
  return Math.max(min, Math.min(max, min - 10 + Math.sqrt(Math.max(1, count)) * 1.75));
}


function getStaticTopicPosition(index: number, total: number) {
  const fourTopicLayout = [
    { x: 30, y: 38 },
    { x: 50, y: 38 },
    { x: 70, y: 38 },
    { x: 50, y: 70 },
  ];

  const threeTopicLayout = [
    { x: 33, y: 50 },
    { x: 50, y: 50 },
    { x: 67, y: 50 },
  ];

  const twoTopicLayout = [
    { x: 40, y: 50 },
    { x: 60, y: 50 },
  ];

  if (total <= 2) return twoTopicLayout[index] ?? { x: 50, y: 50 };
  if (total === 3) return threeTopicLayout[index] ?? { x: 50, y: 50 };
  return fourTopicLayout[index] ?? { x: 50, y: 50 };
}

function getClusterSemanticPosition(
  clusterId: number,
  index: number,
  total: number,
  focusedTopic: boolean
) {
  if (!focusedTopic) {
    return CLUSTER_SEMANTIC_POSITIONS[clusterId] ?? { x: 50, y: 50 };
  }

  const columns = total <= 2 ? total : total <= 4 ? 2 : 3;
  const rows = Math.ceil(total / columns);

  const col = index % columns;
  const row = Math.floor(index / columns);

  const startX = columns === 1 ? 50 : 28;
  const endX = columns === 1 ? 50 : 72;
  const startY = rows === 1 ? 48 : 30;
  const endY = rows === 1 ? 48 : 68;

  const x =
    columns === 1
      ? 50
      : startX + (col * (endX - startX)) / Math.max(1, columns - 1);

  const y =
    rows === 1
      ? 48
      : startY + (row * (endY - startY)) / Math.max(1, rows - 1);

  return { x, y };
}

function getCardSemanticPosition(
  index: number,
  total: number,
  clusterId: number,
  focusedCluster: boolean
) {
  const center = focusedCluster
    ? { x: 50, y: 49 }
    : CLUSTER_SEMANTIC_POSITIONS[clusterId] ?? { x: 50, y: 50 };

  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const safeTotal = Math.max(1, total);
  const angle = index * goldenAngle;

  const progress = Math.sqrt((index + 0.8) / safeTotal);

  const maxRadiusX = focusedCluster ? 48 : 31;
  const maxRadiusY = focusedCluster ? 39 : 25;

  const swirlOffset = focusedCluster ? Math.sin(index * 0.17) * 1.4 : Math.sin(index * 0.14) * 0.8;

  const x = Math.max(
    4,
    Math.min(96, center.x + Math.cos(angle) * maxRadiusX * progress + swirlOffset)
  );

  const y = Math.max(
    8,
    Math.min(89, center.y + Math.sin(angle) * maxRadiusY * progress)
  );

  return { x, y };
}

function makeArcPositions(route: {
  origin_lat: number;
  origin_lon: number;
  receiving_lat: number;
  receiving_lon: number;
}): [number, number][] {
  const startLat = route.origin_lat;
  const startLon = route.origin_lon;
  const endLat = route.receiving_lat;
  const endLon = route.receiving_lon;

  const points: [number, number][] = [];
  const steps = 32;

  const dx = endLon - startLon;
  const dy = endLat - startLat;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const arcHeight = Math.min(18, Math.max(2, distance * 0.12));

  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const lat = startLat + (endLat - startLat) * t;
    const lon = startLon + (endLon - startLon) * t;
    const curve = Math.sin(Math.PI * t) * arcHeight;
    points.push([lat + curve, lon]);
  }

  return points;
}

function interpolateRoutePosition(route: {
  origin_lat: number;
  origin_lon: number;
  receiving_lat: number;
  receiving_lon: number;
  progress?: number;
}): [number, number] {
  const progress = Math.max(0, Math.min(1, route.progress ?? 0));

  return [
    route.origin_lat + (route.receiving_lat - route.origin_lat) * progress,
    route.origin_lon + (route.receiving_lon - route.origin_lon) * progress,
  ];
}

function RouteMapZoomTracker({
  onZoomChange,
}: {
  onZoomChange: (zoom: number) => void;
}) {
  const map = useMap();

  useMapEvents({
    zoomend: () => {
      onZoomChange(map.getZoom());
    },
  });

  useEffect(() => {
    onZoomChange(map.getZoom());
  }, [map, onZoomChange]);

  return null;
}

function DrilldownMapFit({
  data,
  resetSignal,
  selectedRoute,
}: {
  data: MapDrilldownResponse | null;
  resetSignal: number;
  selectedRoute?: any | null;
}) {
  const map = useMap();

  useEffect(() => {
    const bounds: [number, number][] = [];

    if (selectedRoute) {
      bounds.push([selectedRoute.origin_lat, selectedRoute.origin_lon]);
      bounds.push([selectedRoute.receiving_lat, selectedRoute.receiving_lon]);
    } else if (data) {
      data.nodes.forEach((node) => {
        bounds.push([node.lat, node.lon]);
      });

      data.flows.forEach((flow) => {
        bounds.push([flow.origin_lat, flow.origin_lon]);
        bounds.push([flow.receiving_lat, flow.receiving_lon]);
      });

      data.cards.slice(0, 80).forEach((card) => {
        bounds.push([card.origin_lat, card.origin_lon]);
        bounds.push([card.receiving_lat, card.receiving_lon]);
      });
    }

    if (bounds.length === 0) return;

    map.fitBounds(bounds, {
      padding: [55, 55],
      maxZoom: selectedRoute
        ? 5
        : data?.level === "topics"
          ? 3
          : data?.level === "clusters"
            ? 4
            : 5,
    });
  }, [data, map, resetSignal, selectedRoute]);

  return null;
}

function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [topicHierarchy, setTopicHierarchy] = useState(TOPIC_HIERARCHY);

  const [selectedOrigin, setSelectedOrigin] = useState("");
  const [selectedReceiving, setSelectedReceiving] = useState("");
  const [searchText, setSearchText] = useState("");
  const [minDistance, setMinDistance] = useState("");
  const [maxDistance, setMaxDistance] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [topicNodes, setTopicNodes] = useState<DrilldownNode[]>([]);
  const [clusterNodes, setClusterNodes] = useState<DrilldownNode[]>([]);

  const [mapLevel, setMapLevel] = useState<MapLevel>("topics");
  const [selectedMapTopicId, setSelectedMapTopicId] = useState<string | null>(null);
  const [selectedMapCluster, setSelectedMapCluster] = useState<number | null>(null);
  const [selectedPair, setSelectedPair] = useState<SelectedPair | null>(null);
  const [mapDrilldown, setMapDrilldown] = useState<MapDrilldownResponse | null>(null);
  const [mapZoom, setMapZoom] = useState(2);
  const [mapResetSignal, setMapResetSignal] = useState(0);

  const [semanticView, setSemanticView] = useState<"topics" | "clusters" | "cards">("topics");

  const [postcards, setPostcards] = useState<Postcard[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [listOffset, setListOffset] = useState(0);

  const [outliers, setOutliers] = useState<OutlierPostcard[]>([]);
  const [outlierCount, setOutlierCount] = useState(0);
  const [outlierThreshold, setOutlierThreshold] = useState(2.0);

  const [semanticClusterCards, setSemanticClusterCards] = useState<Postcard[]>([]);
  const [semanticClusterTotal, setSemanticClusterTotal] = useState(0);
  const [semanticCardsPage, setSemanticCardsPage] = useState(0);

  const [selectedPostcard, setSelectedPostcard] = useState<Postcard | null>(null);
  const [selectedPostcardRoute, setSelectedPostcardRoute] = useState<any | null>(null);
  const [selectedFlow, setSelectedFlow] = useState<DrilldownFlow | null>(null);

  // === E5 JOURNEY ANIMATION FRONTEND START ===
  const [journeyMode, setJourneyMode] = useState(false);
  const [journeyPeriod, setJourneyPeriod] = useState<"month" | "year">("year");
  const [journeyAnimation, setJourneyAnimation] = useState<JourneyAnimationResponse | null>(null);
  const [journeyFrameIndex, setJourneyFrameIndex] = useState(0);
  const [journeyPlaying, setJourneyPlaying] = useState(false);
  const [journeySpeed, setJourneySpeed] = useState(900);
  // === E5 JOURNEY ANIMATION FRONTEND END ===

  // === E6 TOPIC EVOLUTION STATE START ===
  const [evolutionPeriod, setEvolutionPeriod] = useState<"year" | "month">("year");
  const [evolutionAbstraction, setEvolutionAbstraction] = useState<"topic" | "cluster">("topic");
  const [evolutionCountryRole, setEvolutionCountryRole] = useState<"origin" | "receiving">("receiving");
  const [evolutionCountryA, setEvolutionCountryA] = useState("");
  const [evolutionCountryB, setEvolutionCountryB] = useState("");
  const [topicEvolution, setTopicEvolution] = useState<TopicEvolutionResponse | null>(null);
  // === E6 TOPIC EVOLUTION STATE END ===

  const activeTopic = useMemo(() => {
    if (!selectedMapTopicId) return null;
    return topicHierarchy.find((topic) => topic.id === selectedMapTopicId) ?? null;
  }, [selectedMapTopicId, topicHierarchy]);

  const activeClusterParam =
    selectedMapCluster !== null
      ? String(selectedMapCluster)
      : activeTopic
        ? activeTopic.clusterIds.join(",")
        : "";

  const selectedClusterNode = useMemo(() => {
    if (selectedMapCluster === null) return null;
    return clusterNodes.find((cluster) => cluster.cluster === selectedMapCluster) ?? null;
  }, [clusterNodes, selectedMapCluster]);

  const activeScopeLabel =
    selectedPair !== null
      ? `${selectedPair.origin_country} → ${selectedPair.receiving_country}`
      : selectedClusterNode?.label
        ? selectedClusterNode.label
        : activeTopic?.label ?? "All postcards";

  const currentJourneyFrame = useMemo(() => {
    const frames = journeyAnimation?.frames ?? [];
    if (frames.length === 0) return null;

    const safeIndex = Math.max(0, Math.min(journeyFrameIndex, frames.length - 1));
    return frames[safeIndex] ?? null;
  }, [journeyAnimation, journeyFrameIndex]);

  const evolutionChart = useMemo(() => buildEvolutionChart(topicEvolution), [topicEvolution]);

  const evolutionCountryOptions =
    evolutionCountryRole === "origin"
      ? filterOptions?.origin_countries ?? []
      : filterOptions?.receiving_countries ?? [];

  // === EOE E6 GLOBAL FILTER BRIDGE FRONTEND ===
  // E6 country comparison now acts as part of the shared app scope.
  // This key forces all linked views to refetch when E6 comparison changes.
  const evolutionScopeKey = [
    evolutionCountryRole,
    evolutionCountryA.trim(),
    evolutionCountryB.trim(),
  ].join("|");
  // === EOE E6 GLOBAL FILTER BRIDGE FRONTEND END ===

  function addUniqueCountryValues(values: string[]) {
    return Array.from(
      new Set(values.map((value) => value.trim()).filter(Boolean))
    );
  }

  function setCountryParam(params: URLSearchParams, key: "origin_country" | "receiving_country", values: string[]) {
    const cleaned = addUniqueCountryValues(values);
    if (cleaned.length > 0) {
      params.set(key, cleaned.join(","));
    }
  }

  function addBaseFilterParams(params: URLSearchParams) {
    const compareCountries = [evolutionCountryA, evolutionCountryB];

    if (evolutionCountryRole === "origin") {
      setCountryParam(params, "origin_country", [selectedOrigin, ...compareCountries]);
      setCountryParam(params, "receiving_country", [selectedReceiving]);
    } else {
      setCountryParam(params, "origin_country", [selectedOrigin]);
      setCountryParam(params, "receiving_country", [selectedReceiving, ...compareCountries]);
    }

    if (searchText.trim()) params.set("search", searchText.trim());
    if (minDistance) params.set("min_distance", minDistance);
    if (maxDistance) params.set("max_distance", maxDistance);
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    return params;
  }

  function addScopedFilterParams(params: URLSearchParams) {
    addBaseFilterParams(params);

    if (activeClusterParam) {
      params.set("cluster", activeClusterParam);
    }

    return params;
  }

  function selectPostcardAndShowPath(card: Postcard) {
    setSelectedPostcard(card);
    setSelectedFlow(null);
    setSelectedPostcardRoute(null);
    setMapLevel("cards");
  }

  function resetDrilldown() {
    setMapLevel("topics");
    setSelectedMapTopicId(null);
    setSelectedMapCluster(null);
    setSelectedPair(null);
    setSelectedFlow(null);
    setSelectedPostcard(null);
    setSelectedPostcardRoute(null);
    setSemanticView("topics");
    setListOffset(0);
  }

  function clearFilters() {
    setSelectedOrigin("");
    setSelectedReceiving("");
    setSearchText("");
    setMinDistance("");
    setMaxDistance("");
    setStartDate("");
    setEndDate("");
    setEvolutionCountryA("");
    setEvolutionCountryB("");
    setEvolutionCountryRole("receiving");
    resetDrilldown();
  }

  // === EOE E6 GLOBAL FILTER BRIDGE FRONTEND ===
  function clearCurrentSelectionForEvolutionScope() {
    setSelectedPair(null);
    setSelectedFlow(null);
    setSelectedPostcard(null);
    setSelectedPostcardRoute(null);
    setListOffset(0);
    setJourneyFrameIndex(0);
    setMapResetSignal((value) => value + 1);
  }

  function syncEvolutionPeriod(value: "year" | "month") {
    setEvolutionPeriod(value);
    setJourneyPeriod(value);
    setJourneyFrameIndex(0);
    setJourneyPlaying(false);
  }

  function syncEvolutionAbstraction(value: "topic" | "cluster") {
    setEvolutionAbstraction(value);

    if (value === "topic") {
      setSemanticView("topics");
      setMapLevel("topics");
      setSelectedMapTopicId(null);
      setSelectedMapCluster(null);
    } else {
      setSemanticView("clusters");
      setMapLevel("clusters");
      setSelectedPair(null);
    }

    clearCurrentSelectionForEvolutionScope();
  }

  function syncEvolutionCountryRole(value: "origin" | "receiving") {
    setEvolutionCountryRole(value);
    clearCurrentSelectionForEvolutionScope();
  }

  function syncEvolutionCountryA(value: string) {
    setEvolutionCountryA(value);
    clearCurrentSelectionForEvolutionScope();
  }

  function syncEvolutionCountryB(value: string) {
    setEvolutionCountryB(value);
    clearCurrentSelectionForEvolutionScope();
  }
  // === EOE E6 GLOBAL FILTER BRIDGE FRONTEND END ===

  function openTopic(topicId: string) {
    setSelectedMapTopicId(topicId);
    setSelectedMapCluster(null);
    setSelectedPair(null);
    setSelectedFlow(null);
    setSelectedPostcard(null);
    setSelectedPostcardRoute(null);
    setMapLevel("clusters");
    setSemanticView("clusters");
    setListOffset(0);
  }

  function openCluster(clusterId: number) {
    const cluster = clusterNodes.find((node) => node.cluster === clusterId);

    if (cluster?.topic_group_id) {
      setSelectedMapTopicId(cluster.topic_group_id);
    }

    setSelectedMapCluster(clusterId);
    setSelectedPair(null);
    setSelectedFlow(null);
    setSelectedPostcard(null);
    setSelectedPostcardRoute(null);
    setMapLevel("pairs");
    setSemanticView("cards");
    setListOffset(0);
  }

  function openPair(flow: DrilldownFlow) {
    setSelectedPair({
      origin_iso: flow.origin_iso,
      receiving_iso: flow.receiving_iso,
      origin_country: flow.origin_country,
      receiving_country: flow.receiving_country,
    });

    setSelectedFlow(flow);
    setMapLevel("cards");
    setListOffset(0);
  }

  function goBackOneLevel() {
    if (mapLevel === "cards") {
      setSelectedPair(null);
      setSelectedFlow(null);
      setMapLevel("pairs");
      return;
    }

    if (mapLevel === "pairs") {
      setSelectedMapCluster(null);
      setSelectedFlow(null);
      setSelectedPostcard(null);
    setSelectedPostcardRoute(null);
      setMapLevel("clusters");
      setSemanticView("clusters");
      return;
    }

    if (mapLevel === "clusters") {
      resetDrilldown();
    }
  }

  useEffect(() => {
    fetch(`${API_BASE}/stats`)
      .then((response) => response.json())
      .then((data) => setStats(data))
      .catch(() => setStats(null));

    fetch(`${API_BASE}/filter-options`)
      .then((response) => response.json())
      .then((data) => setFilterOptions(data))
      .catch(() => setFilterOptions(null));
  }, []);

  useEffect(() => {
    const params = addBaseFilterParams(new URLSearchParams());

    fetch(`${API_BASE}/topic-hierarchy?${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        setTopicHierarchy(data.topics?.length ? data.topics : TOPIC_HIERARCHY);
      })
      .catch(() => setTopicHierarchy(TOPIC_HIERARCHY));
  }, [selectedOrigin, selectedReceiving, searchText, minDistance, maxDistance, startDate, endDate, evolutionScopeKey]);

  useEffect(() => {
    const topicParams = addBaseFilterParams(new URLSearchParams());
    topicParams.set("level", "topics");

    fetch(`${API_BASE}/map-drilldown?${topicParams.toString()}`)
      .then((response) => response.json())
      .then((data: MapDrilldownResponse) => setTopicNodes(data.nodes ?? []))
      .catch(() => setTopicNodes([]));

    const clusterParams = addBaseFilterParams(new URLSearchParams());
    clusterParams.set("level", "clusters");

    fetch(`${API_BASE}/map-drilldown?${clusterParams.toString()}`)
      .then((response) => response.json())
      .then((data: MapDrilldownResponse) => setClusterNodes(data.nodes ?? []))
      .catch(() => setClusterNodes([]));
  }, [selectedOrigin, selectedReceiving, searchText, minDistance, maxDistance, startDate, endDate, evolutionScopeKey]);

  useEffect(() => {
    const params = addBaseFilterParams(new URLSearchParams());
    params.set("level", mapLevel);
    params.set("limit", mapLevel === "cards" ? "120" : "80");

    if (selectedMapTopicId) {
      params.set("topic_id", selectedMapTopicId);
    }

    if (selectedMapCluster !== null) {
      params.set("cluster", String(selectedMapCluster));
    }

    if (selectedPair) {
      params.set("origin_iso", selectedPair.origin_iso);
      params.set("receiving_iso", selectedPair.receiving_iso);
    }

    fetch(`${API_BASE}/map-drilldown?${params.toString()}`)
      .then((response) => response.json())
      .then((data: MapDrilldownResponse) => setMapDrilldown(data))
      .catch(() =>
        setMapDrilldown({
          level: mapLevel,
          total_cards: 0,
          breadcrumb: [],
          nodes: [],
          flows: [],
          cards: [],
        })
      );
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
    evolutionScopeKey,
    mapLevel,
    selectedMapTopicId,
    selectedMapCluster,
    selectedPair,
  ]);

  useEffect(() => {
    if (!selectedPostcard?.id) {
      setSelectedPostcardRoute(null);
      return;
    }

    let cancelled = false;

    fetch(`${API_BASE}/postcard-route/${encodeURIComponent(selectedPostcard.id)}`)
      .then((response) => response.json())
      .then((data) => {
        if (cancelled) return;
        const route = data.route ?? null;
        setSelectedPostcardRoute(route);
        if (route) {
          setMapResetSignal((value) => value + 1);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedPostcardRoute(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPostcard?.id]);


  useEffect(() => {
    const params = addScopedFilterParams(new URLSearchParams());

    params.set("period", evolutionPeriod);
    params.set("abstraction", evolutionAbstraction);
    params.set("country_role", evolutionCountryRole);

    if (evolutionCountryA) params.set("country_a", evolutionCountryA);
    if (evolutionCountryB) params.set("country_b", evolutionCountryB);

    fetch(`${API_BASE}/topic-evolution?${params.toString()}`)
      .then((response) => response.json())
      .then((data: TopicEvolutionResponse) => setTopicEvolution(data))
      .catch(() => setTopicEvolution(null));
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
    evolutionScopeKey,
    activeClusterParam,
    evolutionPeriod,
    evolutionAbstraction,
    evolutionCountryRole,
    evolutionCountryA,
    evolutionCountryB,
  ]);

  useEffect(() => {
    const params = addScopedFilterParams(new URLSearchParams());
    params.set("period", journeyPeriod);
    params.set("routes_per_frame", "80");
    params.set("max_frames", journeyPeriod === "year" ? "120" : "72");

    fetch(`${API_BASE}/journey-animation?${params.toString()}`)
      .then((response) => response.json())
      .then((data: JourneyAnimationResponse) => {
        setJourneyAnimation(data);
        setJourneyFrameIndex(0);
      })
      .catch(() => {
        setJourneyAnimation(null);
        setJourneyFrameIndex(0);
      });
  }, [selectedOrigin, selectedReceiving, searchText, minDistance, maxDistance, startDate, endDate, evolutionScopeKey, activeClusterParam, journeyPeriod]);

  useEffect(() => {
    if (!journeyPlaying) return;

    const frames = journeyAnimation?.frames ?? [];
    if (frames.length === 0) return;

    const timer = window.setInterval(() => {
      setJourneyFrameIndex((index) => (index + 1) % frames.length);
    }, journeySpeed);

    return () => window.clearInterval(timer);
  }, [journeyPlaying, journeySpeed, journeyAnimation?.frame_count]);

  useEffect(() => {
    const params = addScopedFilterParams(new URLSearchParams());
    params.set("limit", "36");
    params.set("offset", String(listOffset));

    fetch(`${API_BASE}/postcards?${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        setPostcards(data.postcards ?? []);
        setTotalMatches(data.total_matches ?? 0);
      })
      .catch(() => {
        setPostcards([]);
        setTotalMatches(0);
      });
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
    evolutionScopeKey,
    activeClusterParam,
    listOffset,
  ]);


  useEffect(() => {
    setSemanticCardsPage(0);
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
    evolutionScopeKey,
    activeClusterParam,
    semanticView,
  ]);

  useEffect(() => {
    if (semanticView !== "cards") {
      setSemanticClusterCards([]);
      setSemanticClusterTotal(0);
      return;
    }

    const params = addScopedFilterParams(new URLSearchParams());
    params.set("limit", String(SEMANTIC_CARD_PAGE_SIZE));
    params.set("offset", String(semanticCardsPage * SEMANTIC_CARD_PAGE_SIZE));

    fetch(`${API_BASE}/postcards?${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        setSemanticClusterCards(data.postcards ?? []);
        setSemanticClusterTotal(data.total_matches ?? 0);
      })
      .catch(() => {
        setSemanticClusterCards([]);
        setSemanticClusterTotal(0);
      });
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
    evolutionScopeKey,
    activeClusterParam,
    semanticView,
    semanticCardsPage,
  ]);

  useEffect(() => {
    const params = addScopedFilterParams(new URLSearchParams());
    params.set("threshold", String(outlierThreshold));
    params.set("limit", "24");

    fetch(`${API_BASE}/outliers?${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        setOutliers(data.outliers ?? []);
        setOutlierCount(data.count ?? 0);
      })
      .catch(() => {
        setOutliers([]);
        setOutlierCount(0);
      });
  }, [
    selectedOrigin,
    selectedReceiving,
    searchText,
    minDistance,
    maxDistance,
    startDate,
    endDate,
    evolutionScopeKey,
    activeClusterParam,
    outlierThreshold,
  ]);

  const visibleSemanticTopics = topicNodes.length > 0 ? topicNodes : TOPIC_HIERARCHY.map((topic) => ({
    id: topic.id,
    type: "topic" as const,
    label: topic.label,
    description: topic.description,
    color: topic.color,
    count: 0,
    lat: 0,
    lon: 0,
    clusterIds: topic.clusterIds,
  }));

  const visibleSemanticClusters = clusterNodes.filter((cluster) => {
    if (!selectedMapTopicId) return true;
    return cluster.topic_group_id === selectedMapTopicId;
  });

  const topicPreviewImages = useMemo(() => {
    const previews: Record<string, string[]> = {};

    TOPIC_HIERARCHY.forEach((topic) => {
      previews[topic.id] = visibleSemanticClusters
        .filter((cluster) => cluster.topic_group_id === topic.id)
        .flatMap((cluster) =>
          (cluster.samples ?? [])
            .map((sample) => sample.image_url)
            .filter((imageUrl): imageUrl is string => Boolean(imageUrl))
        )
        .slice(0, 4);
    });

    return previews;
  }, [visibleSemanticClusters]);

  const semanticCards = semanticClusterCards.length
    ? semanticClusterCards
    : postcards;

  const semanticCardsTotal = semanticClusterTotal || totalMatches;

  const countryCount = stats
    ? Math.max(stats.total_origin_countries, stats.total_receiving_countries)
    : 0;

  const mapLevelLabel = selectedPostcardRoute
    ? "Selected postcard path"
    : mapLevel === "topics"
      ? "Topic bubbles"
      : mapLevel === "clusters"
        ? "Cluster bubbles"
        : mapLevel === "pairs"
          ? "Country-pair flows"
          : "Individual cards";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">✉</div>
          <div>
            <h1>Postcard Explorer</h1>
            <p>Semantic visual analytics for Postcrossing data</p>
          </div>
        </div>

        <section className="top-stats">
          <div className="top-stat">
            <span>Total postcards</span>
            <strong>{stats ? compactNumber(stats.total_postcards) : "..."}</strong>
          </div>

          <div className="top-stat">
            <span>Countries</span>
            <strong>{countryCount ? compactNumber(countryCount) : "..."}</strong>
          </div>

          <div className="top-stat">
            <span>Avg distance</span>
            <strong>{stats ? `${compactNumber(Math.round(stats.avg_distance))} km` : "..."}</strong>
          </div>

          <div className="top-stat scope">
            <span>Active scope</span>
            <strong>{activeScopeLabel}</strong>
          </div>
        </section>
      </header>

      <main className="dashboard-layout">
        <aside className="filters-panel">
          <div className="panel-title">
            <h2>Filters</h2>
            <button onClick={clearFilters}>Reset</button>
          </div>

          <label>Search</label>
          <input
            type="text"
            placeholder="mountain, animal, beach, Germany..."
            value={searchText}
            onChange={(event) => {
              setSearchText(event.target.value);
              setListOffset(0);
            }}
          />

          <div className="quick-searches">
            <span>Quick searches</span>
            {["mountain", "animal", "beach", "architecture"].map((term) => (
              <button key={term} onClick={() => setSearchText(term)}>
                {term}
              </button>
            ))}
          </div>

          <label>Source country</label>
          <select
            value={selectedOrigin}
            onChange={(event) => {
              setSelectedOrigin(event.target.value);
              setListOffset(0);
            }}
          >
            <option value="">All source countries</option>
            {filterOptions?.origin_countries.map((country) => (
              <option key={country} value={country}>
                {country}
              </option>
            ))}
          </select>

          <label>Destination country</label>
          <select
            value={selectedReceiving}
            onChange={(event) => {
              setSelectedReceiving(event.target.value);
              setListOffset(0);
            }}
          >
            <option value="">All destination countries</option>
            {filterOptions?.receiving_countries.map((country) => (
              <option key={country} value={country}>
                {country}
              </option>
            ))}
          </select>

          <label>Date range</label>
          <div className="two-field-row">
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </div>

          <label>Distance km</label>
          <div className="two-field-row">
            <input
              type="number"
              placeholder="Min"
              value={minDistance}
              onChange={(event) => setMinDistance(event.target.value)}
            />
            <input
              type="number"
              placeholder="Max"
              value={maxDistance}
              onChange={(event) => setMaxDistance(event.target.value)}
            />
          </div>

          <div className="topic-tree-panel">
            <div className="panel-subtitle">
              <h3>Topic hierarchy</h3>
              <button onClick={resetDrilldown}>All</button>
            </div>

            <div className="topic-tree">
              {topicHierarchy.map((topic) => {
                const topicClusters = clusterNodes.filter((cluster) => cluster.topic_group_id === topic.id);
                const topicCount =
                  topicNodes.find((node) => node.id === topic.id)?.count ??
                  topicClusters.reduce((total, cluster) => total + cluster.count, 0);

                return (
                  <details
                    key={topic.id}
                    className={selectedMapTopicId === topic.id ? "topic-tree-group active" : "topic-tree-group"}
                    open={selectedMapTopicId === topic.id || topic.id === "blue_nature"}
                  >
                    <summary>
                      <span className="topic-folder" style={{ background: topic.color }} />
                      <strong>{topic.label}</strong>
                      <em>{compactNumber(topicCount)}</em>
                    </summary>

                    <button className="topic-tree-action" onClick={() => openTopic(topic.id)}>
                      Open topic
                    </button>

                    <div className="topic-tree-children">
                      {topicClusters.map((cluster) => (
                        <button
                          key={cluster.id}
                          className={selectedMapCluster === cluster.cluster ? "selected" : ""}
                          onClick={() => {
                            if (cluster.cluster !== undefined) openCluster(cluster.cluster);
                          }}
                        >
                          <i style={{ background: cluster.color }} />
                          <span>{cluster.label}</span>
                          <strong>{compactNumber(cluster.count)}</strong>
                        </button>
                      ))}
                    </div>
                  </details>
                );
              })}
            </div>
          </div>

          <div className="result-card">
            <span>Filtered result</span>
            <strong>{compactNumber(totalMatches)}</strong>
            <p>postcards matched</p>
          </div>
        </aside>

        <section className="workspace">
          <section className="card topic-space-card">
            <div className="section-header">
              <div>
                <h2>Image Topic Space <span>semantic canvas</span></h2>
                <p>
                  Click progressively: topic → cluster → cards. The canvas stays semantic; the map stays geographic.
                </p>
              </div>

              <div className="semantic-controls">
                  <span>View</span>
                <button
                  className={semanticView === "topics" ? "active" : ""}
                  onClick={() => setSemanticView("topics")}
                >
                  Topics
                </button>
                <button
                  className={semanticView === "clusters" ? "active" : ""}
                  onClick={() => setSemanticView("clusters")}
                >
                  Clusters
                </button>
                <button
                  className={semanticView === "cards" ? "active" : ""}
                  onClick={() => setSemanticView("cards")}
                  >
                  Cards
                  </button>
                </div>
              </div>

            <div className={`semantic-canvas semantic-canvas-${semanticView}`}>
              {semanticView === "topics" &&
                visibleSemanticTopics.map((node, index) => {
                  const semanticPosition = getStaticTopicPosition(index, visibleSemanticTopics.length);
                  const topicWidth = 210;
                  const topicHeight = 122;
                  const previewImages = topicPreviewImages[node.id] ?? [];

                  return (
                    <button
                      key={node.id}
                      className="semantic-node topic-node static-topic-node"
                      style={
                        {
                          left: `${semanticPosition?.x ?? 50}%`,
                          top: `${semanticPosition?.y ?? 50}%`,
                          width: topicWidth,
                          height: topicHeight,
                          "--node-color": node.color,
                        } as CSSProperties
                      }
                      onClick={() => openTopic(node.id)}
                    >
                      {previewImages.length > 0 && (
                        <div className="topic-node-photos">
                          {previewImages.map((imageUrl, idx) => (
                            <img
                              key={`${node.id}-${idx}`}
                              src={`${API_BASE}${imageUrl}`}
                              alt={node.label}
                            />
                          ))}
                        </div>
                      )}

                      <strong>{node.label}</strong>
                      <span>{compactNumber(node.count)} cards</span>
                    </button>
                  );
                })}

              {semanticView === "clusters" &&
                visibleSemanticClusters.map((node, index) => {
                  const clusterId = node.cluster ?? 0;
                  const position = getClusterSemanticPosition(
                    clusterId,
                    index,
                    visibleSemanticClusters.length,
                    Boolean(selectedMapTopicId)
                  );
                  const size = semanticSize(node.count, 100, 165);

                  return (
                    <button
                      key={node.id}
                      className="semantic-node cluster-node"
                      style={
                        {
                          left: `${position.x}%`,
                          top: `${position.y}%`,
                          width: size,
                          height: size,
                          "--node-color": node.color,
                        } as CSSProperties
                      }
                      onClick={() => openCluster(clusterId)}
                    >
                      <div className="cluster-sample-strip">
                        {node.samples?.slice(0, 4).map((sample) => (
                          sample.image_url ? (
                            <img
                              key={sample.id}
                              src={`${API_BASE}${sample.image_url}`}
                              alt={sample.id}
                            />
                          ) : null
                        ))}
                      </div>

                      <strong>{node.label}</strong>
                      <span>{compactNumber(node.count)} cards</span>
                    </button>
                  );
                })}

              {semanticView === "cards" &&
                semanticCards.map((card, index) => {
                  const clusterId = card.cluster ?? selectedMapCluster ?? 0;
                  const displayedTotal = semanticCards.length;
                  const position = getCardSemanticPosition(
                    index,
                    displayedTotal,
                    clusterId,
                    selectedMapCluster !== null
                  );

                  const cardWidth =
                    displayedTotal > 700 ? 22 :
                    displayedTotal > 450 ? 26 :
                    displayedTotal > 250 ? 31 :
                    40;

                  const cardHeight =
                    displayedTotal > 700 ? 17 :
                    displayedTotal > 450 ? 20 :
                    displayedTotal > 250 ? 24 :
                    30;

                  return (
                    <button
                      key={`${semanticCardsPage}-${card.id}`}
                      className={selectedPostcard?.id === card.id ? "semantic-card-point selected" : "semantic-card-point"}
                      style={
                        {
                          left: `${position.x}%`,
                          top: `${position.y}%`,
                          "--node-color": card.cluster_color || "#64748b",
                          "--card-w": `${cardWidth}px`,
                          "--card-h": `${cardHeight}px`,
                        } as CSSProperties
                      }
                      onClick={() => selectPostcardAndShowPath(card)}
                      title={`${card.id} — ${card.cluster_name ?? ""}`}
                    >
                      {card.image_url && displayedTotal <= 1000 ? (
                        <img src={`${API_BASE}${card.image_url}`} alt={card.id} />
                      ) : (
                        <span />
                      )}
                    </button>
                  );
                })}

              {semanticView === "cards" && (
                <div className="semantic-pagination">
                  <button
                    onClick={() => { setSelectedPostcard(null);
    setSelectedPostcardRoute(null); setSemanticCardsPage((page) => Math.max(0, page - 1)); }}
                    disabled={semanticCardsPage === 0}
                  >
                    Back
                  </button>

                  <div>
                    <strong>
                      {compactNumber(
                        semanticCards.length === 0
                          ? 0
                          : semanticCardsPage * SEMANTIC_CARD_PAGE_SIZE + 1
                      )}
                      –
                      {compactNumber(
                        Math.min(
                          semanticClusterTotal || semanticCardsTotal,
                          semanticCardsPage * SEMANTIC_CARD_PAGE_SIZE + semanticCards.length
                        )
                      )}
                    </strong>
                    <span>
                      of {compactNumber(semanticClusterTotal || semanticCardsTotal)} cards
                    </span>
                  </div>

                  <button
                    onClick={() => { setSelectedPostcard(null);
    setSelectedPostcardRoute(null); setSemanticCardsPage((page) => page + 1); }}
                    disabled={
                      (semanticCardsPage + 1) * SEMANTIC_CARD_PAGE_SIZE >=
                      (semanticClusterTotal || semanticCardsTotal)
                    }
                  >
                    Next
                  </button>
                </div>
              )}

              <div className="semantic-axis horizontal" />
              <div className="semantic-axis vertical" />
              <p className="semantic-hint">similar visual topics are placed close together</p>
            </div>
          </section>

          <section className="card journey-section">
            <div className="section-header map-title-row">
              <div>
                <h2>Postcard Journeys <span>drill-down map</span></h2>
                <p>
                  Level: <strong>{mapLevelLabel}</strong>. The map starts clean and reveals detail only after clicks.
                </p>
              </div>

              <div className="map-mode-badge">
                <span>Current map level</span>
                <strong>{mapLevelLabel}</strong>
              </div>

              <button className="reset-zoom-button" onClick={() => setMapResetSignal((value) => value + 1)}>
                Reset zoom
              </button>
            </div>

            <div className="map-breadcrumb">
              <button onClick={resetDrilldown}>Topics</button>

              {selectedMapTopicId && (
                <button onClick={() => {
                  setMapLevel("clusters");
                  setSelectedMapCluster(null);
                  setSelectedPair(null);
                  setSelectedFlow(null);
                }}>
                  {activeTopic?.label ?? "Topic"}
                </button>
              )}

              {selectedMapCluster !== null && (
                <button onClick={() => {
                  setMapLevel("pairs");
                  setSelectedPair(null);
                  setSelectedFlow(null);
                }}>
                  {selectedClusterNode?.label ?? `Cluster ${selectedMapCluster}`}
                </button>
              )}

              {selectedPair && (
                <button onClick={() => setMapLevel("cards")}>
                  {selectedPair.origin_country} → {selectedPair.receiving_country}
                </button>
              )}

              {mapLevel !== "topics" && (
                <button className="breadcrumb-back" onClick={goBackOneLevel}>
                  Back
                </button>
              )}
            </div>

            <div className="journey-animation-panel">
              <div>
                <strong>E5 Journey Animation</strong>
                <span>
                  {currentJourneyFrame
                    ? `${currentJourneyFrame.period}: ${compactNumber(currentJourneyFrame.active_count)} active, ${compactNumber(currentJourneyFrame.sent_count)} sent, ${compactNumber(currentJourneyFrame.received_count)} received`
                    : "No animation frame loaded"}
                </span>
              </div>

              <button
                className={journeyMode ? "active" : ""}
                onClick={() => {
                  setJourneyMode((value) => !value);
                  setSelectedPostcard(null);
                  setSelectedPostcardRoute(null);
                }}
              >
                {journeyMode ? "Animation on" : "Animation off"}
              </button>

              <button onClick={() => setJourneyPlaying((value) => !value)} disabled={!journeyMode || !journeyAnimation?.frames?.length}>
                {journeyPlaying ? "Pause" : "Play"}
              </button>

              <label>
                Period
                <select value={journeyPeriod} onChange={(event) => setJourneyPeriod(event.target.value as "month" | "year")}>
                  <option value="year">Year</option>
                  <option value="month">Month</option>
                </select>
              </label>

              <label>
                Speed
                <select value={journeySpeed} onChange={(event) => setJourneySpeed(Number(event.target.value))}>
                  <option value={1400}>Slow</option>
                  <option value={900}>Normal</option>
                  <option value={450}>Fast</option>
                </select>
              </label>

              <input
                type="range"
                min={0}
                max={Math.max(0, (journeyAnimation?.frames?.length ?? 1) - 1)}
                value={journeyFrameIndex}
                onChange={(event) => setJourneyFrameIndex(Number(event.target.value))}
                disabled={!journeyAnimation?.frames?.length}
              />
            </div>

            <div className="journey-map-layout">
              <div className="map-tree-sidebar">
                <h3>Drill-down tree</h3>
                <p>
                  Do not show everything at once. Click one level to reveal the next level.
                </p>

                <div className="drilldown-summary">
                  <span>Current level</span>
                  <strong>{mapLevelLabel}</strong>
                  <em>{compactNumber(mapDrilldown?.total_cards ?? 0)} cards in scope</em>
                </div>

                <div className="map-tree-list">
                  {mapLevel === "topics" &&
                    mapDrilldown?.nodes.map((node) => (
                      <button key={node.id} className="drilldown-list-item" onClick={() => openTopic(node.id)}>
                        <i style={{ background: node.color }} />
                        <span>{node.label}</span>
                        <strong>{compactNumber(node.count)}</strong>
                      </button>
                    ))}

                  {mapLevel === "clusters" &&
                    mapDrilldown?.nodes.map((node) => (
                      <button
                        key={node.id}
                        className="drilldown-list-item"
                        onClick={() => {
                          if (node.cluster !== undefined) openCluster(node.cluster);
                        }}
                      >
                        <i style={{ background: node.color }} />
                        <span>{node.label}</span>
                        <strong>{compactNumber(node.count)}</strong>
                      </button>
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "pairs" &&
                    mapDrilldown?.flows.map((flow) => (
                      <button key={flow.id} className="drilldown-list-item" onClick={() => openPair(flow)}>
                        <i style={{ background: flow.cluster_color }} />
                        <span>{flow.origin_country} → {flow.receiving_country}</span>
                        <strong>{compactNumber(flow.route_count)}</strong>
                      </button>
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "cards" &&
                    mapDrilldown?.cards.map((card) => (
                      <button
                        key={card.id}
                        className="drilldown-card-item"
                        onClick={() => selectPostcardAndShowPath(card)}
                      >
                        {card.image_url && <img src={`${API_BASE}${card.image_url}`} alt={card.id} />}
                        <span>{card.id}</span>
                        <strong>{Math.round(card.time)} d</strong>
                      </button>
                    ))}
                </div>
              </div>

              <div className="journey-map-wrap">
                <MapContainer
                  center={[25, 10]}
                  zoom={1}
                  minZoom={1}
                  maxZoom={7}
                  maxBounds={[
                    [-85, -180],
                    [85, 180],
                  ]}
                  maxBoundsViscosity={1.0}
                  scrollWheelZoom={true}
                  worldCopyJump={false}
                  className="route-map"
                >
                  <TileLayer
                    attribution="&copy; OpenStreetMap contributors &copy; CARTO"
                    url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                    noWrap={true}
                  />

                  <RouteMapZoomTracker onZoomChange={setMapZoom} />
                  <DrilldownMapFit data={mapDrilldown} resetSignal={mapResetSignal} selectedRoute={selectedPostcardRoute} />

                  {journeyMode &&
                    currentJourneyFrame?.routes.map((route) => (
                      <Polyline
                        key={`journey-line-${currentJourneyFrame.period}-${route.id}`}
                        positions={makeArcPositions(route)}
                        pathOptions={{
                          color: route.cluster_color || "#2563eb",
                          weight: 2.2,
                          opacity: 0.36,
                        }}
                      >
                        <Popup>
                          <div className="route-popup">
                            <strong>{route.id}</strong>
                            <p>{route.origin_country} → {route.receiving_country}</p>
                            <p>{route.topic_group_name}</p>
                            <p>Frame: {currentJourneyFrame.period}</p>
                          </div>
                        </Popup>
                      </Polyline>
                    ))}

                  {journeyMode &&
                    currentJourneyFrame?.routes.map((route) => (
                      <CircleMarker
                        key={`journey-moving-${currentJourneyFrame.period}-${route.id}`}
                        center={interpolateRoutePosition(route)}
                        radius={5}
                        pathOptions={{
                          color: "#ffffff",
                          fillColor: route.cluster_color || "#2563eb",
                          fillOpacity: 0.95,
                          weight: 1.6,
                        }}
                      >
                        <Tooltip direction="top" offset={[0, -8]}>
                          {route.id} — {Math.round((route.progress ?? 0) * 100)}%
                        </Tooltip>
                      </CircleMarker>
                    ))}

                  {!journeyMode && selectedPostcardRoute && (
                    <Polyline
                      key={`selected-route-${selectedPostcardRoute.id}`}
                      positions={makeArcPositions(selectedPostcardRoute)}
                      pathOptions={{
                        color: selectedPostcardRoute.cluster_color || "#c1622d",
                        weight: 5.5,
                        opacity: 0.92,
                      }}
                    >
                      <Popup>
                        <div className="route-popup">
                          <strong>{selectedPostcardRoute.id}</strong>
                          <p>
                            {selectedPostcardRoute.origin_country} → {selectedPostcardRoute.receiving_country}
                          </p>
                          <p>{Math.round(selectedPostcardRoute.distance).toLocaleString()} km</p>
                          <p>{Math.round(selectedPostcardRoute.time)} days</p>
                        </div>
                      </Popup>
                    </Polyline>
                  )}

                  {!journeyMode && selectedPostcardRoute && (
                    <CircleMarker
                      key={`selected-origin-${selectedPostcardRoute.id}`}
                      center={[selectedPostcardRoute.origin_lat, selectedPostcardRoute.origin_lon]}
                      radius={7}
                      pathOptions={{
                        color: "#ffffff",
                        fillColor: selectedPostcardRoute.cluster_color || "#c1622d",
                        fillOpacity: 0.95,
                        weight: 2,
                      }}
                    >
                      <Tooltip direction="top" offset={[0, -8]}>
                        Origin: {selectedPostcardRoute.origin_country}
                      </Tooltip>
                    </CircleMarker>
                  )}

                  {!journeyMode && selectedPostcardRoute && (
                    <CircleMarker
                      key={`selected-destination-${selectedPostcardRoute.id}`}
                      center={[selectedPostcardRoute.receiving_lat, selectedPostcardRoute.receiving_lon]}
                      radius={6}
                      pathOptions={{
                        color: "#ffffff",
                        fillColor: "#111827",
                        fillOpacity: 0.9,
                        weight: 2,
                      }}
                    >
                      <Tooltip direction="top" offset={[0, -8]}>
                        Destination: {selectedPostcardRoute.receiving_country}
                      </Tooltip>
                    </CircleMarker>
                  )}

                  {!journeyMode && !selectedPostcardRoute && (mapLevel === "topics" || mapLevel === "clusters") &&
                    mapDrilldown?.nodes.map((node) => (
                      <CircleMarker
                        key={node.id}
                        center={[node.lat, node.lon]}
                        radius={node.type === "topic" ? mapNodeRadius(node.count) : clusterNodeRadius(node.count)}
                        eventHandlers={{
                          click: () => {
                            if (node.type === "topic") openTopic(node.id);
                            if (node.type === "cluster" && node.cluster !== undefined) openCluster(node.cluster);
                          },
                        }}
                        pathOptions={{
                          color: "#ffffff",
                          fillColor: node.color,
                          fillOpacity: 0.68,
                          weight: 3,
                        }}
                      >
                        <Tooltip permanent direction="center" className="map-node-label">
                          <span>{node.label}</span>
                          <strong>{compactNumber(node.count)}</strong>
                        </Tooltip>

                        <Popup>
                          <div className="route-popup">
                            <strong>{node.label}</strong>
                            <p>{compactNumber(node.count)} postcards</p>
                            {node.description && <p>{node.description}</p>}
                            <p>Click to open next level.</p>
                          </div>
                        </Popup>
                      </CircleMarker>
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "pairs" &&
                    mapDrilldown?.flows.map((flow) => (
                      <Polyline
                        key={flow.id}
                        positions={makeArcPositions(flow)}
                        eventHandlers={{
                          click: () => openPair(flow),
                        }}
                        pathOptions={{
                          color: flow.cluster_color || "#2563eb",
                          weight: lineWeight(flow.route_count),
                          opacity: 0.52,
                        }}
                      >
                        <Popup>
                          <div className="route-popup">
                            <strong>{flow.route_count} postcards</strong>
                            <p>{flow.origin_country} → {flow.receiving_country}</p>
                            <p>{flow.cluster_name}</p>
                            <p>Avg time: {Math.round(flow.avg_time)} days</p>
                            <p>Click to open individual cards.</p>
                          </div>
                        </Popup>
                      </Polyline>
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "pairs" &&
                    mapDrilldown?.flows.map((flow) => (
                      <CircleMarker
                        key={`origin-${flow.id}`}
                        center={[flow.origin_lat, flow.origin_lon]}
                        radius={Math.max(4, Math.min(14, 4 + Math.sqrt(flow.route_count) * 0.38))}
                        pathOptions={{
                          color: "#ffffff",
                          fillColor: flow.cluster_color || "#2563eb",
                          fillOpacity: 0.9,
                          weight: 1.6,
                        }}
                      />
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "pairs" &&
                    mapDrilldown?.flows.map((flow) => (
                      <CircleMarker
                        key={`destination-${flow.id}`}
                        center={[flow.receiving_lat, flow.receiving_lon]}
                        radius={4}
                        pathOptions={{
                          color: "#ffffff",
                          fillColor: "#111827",
                          fillOpacity: 0.75,
                          weight: 1.3,
                        }}
                      />
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "cards" &&
                    mapDrilldown?.cards.map((card) => (
                      <Polyline
                        key={`card-line-${card.id}`}
                        positions={makeArcPositions(card)}
                        eventHandlers={{
                          click: () => selectPostcardAndShowPath(card),
                        }}
                        pathOptions={{
                          color: card.cluster_color || "#2563eb",
                          weight: selectedPostcard?.id === card.id ? 4.5 : 1.8,
                          opacity: selectedPostcard?.id === card.id ? 0.9 : 0.38,
                        }}
                      >
                        <Popup>
                          <div className="route-popup">
                            <strong>{card.id}</strong>
                            <p>{card.origin_country} → {card.receiving_country}</p>
                            <p>{Math.round(card.distance).toLocaleString()} km</p>
                            <p>{Math.round(card.time)} days</p>
                          </div>
                        </Popup>
                      </Polyline>
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "cards" &&
                    mapDrilldown?.cards.map((card) => (
                      <CircleMarker
                        key={`card-origin-${card.id}`}
                        center={[card.origin_lat, card.origin_lon]}
                        radius={4}
                        eventHandlers={{
                          click: () => selectPostcardAndShowPath(card),
                        }}
                        pathOptions={{
                          color: "#ffffff",
                          fillColor: card.cluster_color || "#2563eb",
                          fillOpacity: 0.9,
                          weight: 1.5,
                        }}
                      />
                    ))}

                  {!journeyMode && !selectedPostcardRoute && mapLevel === "cards" &&
                    mapDrilldown?.cards.map((card) => (
                      <CircleMarker
                        key={`card-destination-${card.id}`}
                        center={[card.receiving_lat, card.receiving_lon]}
                        radius={3.5}
                        pathOptions={{
                          color: "#ffffff",
                          fillColor: "#111827",
                          fillOpacity: 0.75,
                          weight: 1.2,
                        }}
                      />
                    ))}
                </MapContainer>

                <div className="map-overlay-legend">
                  <strong>{selectedPostcardRoute ? "Selected path" : "Map logic"}</strong>
                  <span><i className="origin-dot" /> {selectedPostcardRoute ? "Only selected postcard is shown" : "Click bubble to open next level"}</span>
                  <span><i className="flow-dot" /> Lines appear only at country-pair level</span>
                  <span><i className="destination-dot" /> Black dot = destination</span>
                  <small>Zoom: {mapZoom}</small>
                </div>
              </div>
            </div>
          </section>


          <section className="card evolution-section">
            <div className="section-header">
              <div>
                <h2>Topic Evolution <span>stream graph</span></h2>
                <p>
                  Shows how visual topic groups change over time. Use abstraction and country comparison controls.
                </p>
              </div>

              <div className="map-mode-badge">
                <span>Total in scope</span>
                <strong>{compactNumber(topicEvolution?.total_cards ?? 0)}</strong>
              </div>
            </div>

            <div className="evolution-controls">
              <label>
                Period
                <select value={evolutionPeriod} onChange={(event) => syncEvolutionPeriod(event.target.value as "year" | "month")}>
                  <option value="year">Year</option>
                  <option value="month">Month</option>
                </select>
              </label>

              <label>
                Abstraction
                <select value={evolutionAbstraction} onChange={(event) => syncEvolutionAbstraction(event.target.value as "topic" | "cluster")}>
                  <option value="topic">Topic groups</option>
                  <option value="cluster">Clusters</option>
                </select>
              </label>

              <label>
                Country role
                <select value={evolutionCountryRole} onChange={(event) => syncEvolutionCountryRole(event.target.value as "origin" | "receiving")}>
                  <option value="receiving">Destination country</option>
                  <option value="origin">Source country</option>
                </select>
              </label>

              <label>
                Compare A
                <input
                  list="evolution-country-options"
                  value={evolutionCountryA}
                  onChange={(event) => syncEvolutionCountryA(event.target.value)}
                  placeholder="Country A"
                />
              </label>

              <label>
                Compare B
                <input
                  list="evolution-country-options"
                  value={evolutionCountryB}
                  onChange={(event) => syncEvolutionCountryB(event.target.value)}
                  placeholder="Country B"
                />
              </label>

              <datalist id="evolution-country-options">
                {evolutionCountryOptions.map((country) => (
                  <option key={country} value={country} />
                ))}
              </datalist>
            </div>

            <div className="evolution-chart-wrap">
              {evolutionChart.layers.length > 0 ? (
                <svg
                  className="evolution-chart"
                  viewBox={`0 0 ${evolutionChart.width} ${evolutionChart.height}`}
                  role="img"
                >
                  {evolutionChart.layers.map((layer) => (
                    <path
                      key={layer.id}
                      d={layer.path}
                      fill={layer.color}
                      opacity={0.72}
                    />
                  ))}

                  {evolutionChart.periods.map((period, index) => {
                    const step = Math.max(1, Math.ceil(evolutionChart.periods.length / 8));
                    if (index % step !== 0 && index !== evolutionChart.periods.length - 1) return null;

                    const x =
                      evolutionChart.periods.length <= 1
                        ? 410
                        : 42 + (index * (820 - 42 - 18)) / Math.max(1, evolutionChart.periods.length - 1);

                    return (
                      <text key={period} x={x} y={238} textAnchor="middle" className="evolution-axis-label">
                        {period}
                      </text>
                    );
                  })}
                </svg>
              ) : (
                <div className="evolution-empty">No topic evolution data in current scope.</div>
              )}

              <div className="evolution-legend">
                {evolutionChart.layers.map((layer) => (
                  <div key={layer.id}>
                    <i style={{ background: layer.color }} />
                    <span>{layer.label}</span>
                    <strong>{compactNumber(layer.total)}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="evolution-comparison">
              <div>
                <span>{evolutionCountryA || "Country A"}</span>
                <strong>{compactNumber(evolutionChart.countryATotal)}</strong>
              </div>
              <div>
                <span>{evolutionCountryB || "Country B"}</span>
                <strong>{compactNumber(evolutionChart.countryBTotal)}</strong>
              </div>
            </div>
          </section>

          <section className="lower-grid">
            <section className="card outlier-section">
              <div className="section-header">
                <div>
                  <h2>Long-arrival Outliers</h2>
                  <p>Cards that took exceedingly long to arrive</p>
                </div>

                <div className="outlier-threshold-control">
                  <label>Z threshold</label>
                  <select value={outlierThreshold} onChange={(event) => setOutlierThreshold(Number(event.target.value))}>
                    <option value={1.5}>1.5</option>
                    <option value={2.0}>2.0</option>
                    <option value={2.5}>2.5</option>
                    <option value={3.0}>3.0</option>
                  </select>
                </div>
              </div>

              <div className="outlier-summary">
                <strong>{compactNumber(outlierCount)}</strong>
                <span>long-arrival cards in current scope</span>
              </div>

              <div className="outlier-grid">
                {outliers.map((outlier) => (
                  <button
                    key={outlier.id}
                    className={selectedPostcard?.id === outlier.id ? "selected outlier-card" : "outlier-card"}
                    onClick={() => selectPostcardAndShowPath(outlier)}
                  >
                    {outlier.image_url && <img src={`${API_BASE}${outlier.image_url}`} alt={outlier.id} />}
                    <div>
                      <strong>{outlier.id}</strong>
                      <span>{Math.round(outlier.time)} days</span>
                      <p>{outlier.origin_country} → {outlier.receiving_country}</p>
                    </div>
                  </button>
                ))}
              </div>
            </section>

            <section className="card list-section">
              <div className="section-header">
                <div>
                  <h2>Postcards List</h2>
                  <p>Scrollable metadata view for current filters</p>
                </div>

                <div className="list-actions">
                  <button disabled={listOffset === 0} onClick={() => setListOffset(Math.max(0, listOffset - 36))}>
                    Previous
                  </button>
                  <button disabled={listOffset + 36 >= totalMatches} onClick={() => setListOffset(listOffset + 36)}>
                    Next
                  </button>
                </div>
              </div>

              <div className="postcard-grid">
                {postcards.map((card) => (
                  <button
                    key={card.id}
                    className={selectedPostcard?.id === card.id ? "selected postcard-card" : "postcard-card"}
                    onClick={() => selectPostcardAndShowPath(card)}
                  >
                    {card.image_url && <img src={`${API_BASE}${card.image_url}`} alt={card.id} />}
                    <div>
                      <h3>{card.id}</h3>
                      <p>{card.origin_country} → {card.receiving_country}</p>
                      <small>{Math.round(card.distance).toLocaleString()} km | {Math.round(card.time)} days</small>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </section>
        </section>

        <aside className="detail-panel">
          <div className="detail-header">
            <h2>Selected Postcard</h2>
            <span />
          </div>

          {!selectedPostcard ? (
            <div className="detail-empty">
              <p>Select a postcard, cluster image, outlier, or map route to inspect details.</p>
            </div>
          ) : (
            <>
              {selectedPostcard.image_url && (
                <img className="detail-image" src={`${API_BASE}${selectedPostcard.image_url}`} alt={selectedPostcard.id} />
              )}

              <div className="topic-tags">
                {selectedPostcard.topic_group_name && (
                  <span style={{ background: selectedPostcard.topic_group_color || "#16a34a" }}>
                    {selectedPostcard.topic_group_name}
                  </span>
                )}
                {selectedPostcard.cluster_name && (
                  <span style={{ background: selectedPostcard.cluster_color || "#2563eb" }}>
                    {selectedPostcard.cluster_name}
                  </span>
                )}
              </div>

              <div className="detail-table">
                <div>
                  <span>Postcard ID</span>
                  <strong>{selectedPostcard.id}</strong>
                </div>
                <div>
                  <span>Origin</span>
                  <strong>{selectedPostcard.origin_city || "Unknown"}, {selectedPostcard.origin_country}</strong>
                </div>
                <div>
                  <span>Destination</span>
                  <strong>{selectedPostcard.receiving_city || "Unknown"}, {selectedPostcard.receiving_country}</strong>
                </div>
                <div>
                  <span>Sent date</span>
                  <strong>{selectedPostcard.date_sent || "Unknown"}</strong>
                </div>
                <div>
                  <span>Received date</span>
                  <strong>{selectedPostcard.date_received || "Unknown"}</strong>
                </div>
                <div>
                  <span>Travel distance</span>
                  <strong>{Math.round(selectedPostcard.distance).toLocaleString()} km</strong>
                </div>
                <div>
                  <span>Travel time</span>
                  <strong>{Math.round(selectedPostcard.time)} days</strong>
                </div>
              </div>

              <div className="detail-actions">
                <button
                  onClick={() => {
                    if (selectedPostcard.cluster !== undefined) {
                      openCluster(selectedPostcard.cluster);
                    }
                  }}
                >
                  Open Cluster
                </button>
                <button onClick={() => setSelectedPostcard(null)}>Clear</button>
              </div>
            </>
          )}

          {selectedFlow && (
            <div className="selected-route-panel">
              <h3>Selected country-pair flow</h3>
              <p>{selectedFlow.origin_country} → {selectedFlow.receiving_country}</p>
              <strong>{selectedFlow.route_count} postcards in this bundle</strong>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

export default App;
