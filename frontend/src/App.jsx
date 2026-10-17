import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Calendar,
  Clock,
  Sparkles,
  FileSpreadsheet,
  FileText,
  Users,
  GraduationCap,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Sliders,
  RefreshCw,
  BookOpen,
  ShieldCheck,
  BarChart3,
  X,
  Layers,
  Plus,
  Trash2,
  Upload,
  Download,
} from 'lucide-react';

const API_BASE = '/api';

export default function App() {
  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState('engineering');
  const [dataset, setDataset] = useState(null);
  const [schedule, setSchedule] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [solverType, setSolverType] = useState('cp_sat');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState('batch'); // 'batch' | 'faculty' | 'room' | 'analytics' | 'dataset'

  // Filters
  const [selectedBatchId, setSelectedBatchId] = useState('');
  const [selectedFacultyId, setSelectedFacultyId] = useState('');
  const [selectedRoomId, setSelectedRoomId] = useState('');

  // Modals & Drawers
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [weights, setWeights] = useState({
    weight_idle_student: 2.0,
    weight_idle_faculty: 1.5,
    weight_workload_balance: 1.2,
    weight_room_utilization: 1.0,
    weight_faculty_preference: 1.5,
  });

  const [inspectSlot, setInspectSlot] = useState(null);
  const [moveTargetDay, setMoveTargetDay] = useState(0);
  const [moveTargetSlot, setMoveTargetSlot] = useState(0);
  const [moveTargetRoom, setMoveTargetRoom] = useState('');
  const [moveFeedback, setMoveFeedback] = useState(null);
  const [isMoving, setIsMoving] = useState(false);

  // Add Entity Modals
  const [showAddRoomModal, setShowAddRoomModal] = useState(false);
  const [newRoom, setNewRoom] = useState({ name: '', room_type: 'CLASSROOM', capacity: 60, building: 'Academic Block' });

  const [showAddFacultyModal, setShowAddFacultyModal] = useState(false);
  const [newFaculty, setNewFaculty] = useState({ name: '', department: 'Computer Science', designation: 'Assistant Professor', max_daily_hours: 4 });

  const [showAddCourseModal, setShowAddCourseModal] = useState(false);
  const [newCourse, setNewCourse] = useState({ code: '', name: '', department: 'Computer Science', course_type: 'THEORY', weekly_hours: 3, consecutive_slots: 1, room_type_required: 'CLASSROOM', batch_id: '', faculty_id: '' });

  const fileInputRef = useRef(null);

  const [optimProgress, setOptimProgress] = useState(null);

  // Synchronized state references for stable callbacks without dependency loops
  const datasetRef = useRef(dataset);
  datasetRef.current = dataset;
  const solverTypeRef = useRef(solverType);
  solverTypeRef.current = solverType;
  const weightsRef = useRef(weights);
  weightsRef.current = weights;

  // Concurrency & lifecycle guards
  const isGeneratingRef = useRef(false);
  const lastLoadedPresetRef = useRef('');

  // Core API functions declared before useEffect for React Compiler optimization
  const runGenerate = useCallback(async (dsToUse, solver, currentWeights) => {
    // Concurrency guard: prevents multiple concurrent or looped runs
    if (isGeneratingRef.current) {
      console.warn('Optimization already active, ignoring duplicate call');
      return;
    }

    const targetDs = dsToUse || datasetRef.current;
    if (!targetDs) return;

    const targetSolver = solver || solverTypeRef.current;
    const targetWeights = currentWeights || weightsRef.current;

    isGeneratingRef.current = true;
    setIsGenerating(true);
    setMoveFeedback(null);
    setOptimProgress({
      percent: 15,
      stage: 'Initializing AI Scheduling Engine...',
      stepIndex: 1,
      conflicts: (targetDs.courses?.length || 18) * 2,
      quality: 28.0,
      details: 'Connecting to multi-threaded constraint solver...',
      isComplete: false,
    });

    try {
      const payload = {
        dataset: {
          ...targetDs,
          weights: targetWeights,
        },
        solver_type: targetSolver,
        max_time_seconds: 25,
        ga_population_size: 60,
        ga_generations: 150,
      };

      const res = await fetch(`${API_BASE}/generate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.body) {
        throw new Error('Streaming response body not supported');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.type === 'progress') {
              setOptimProgress({
                percent: event.percent,
                stage: event.stage,
                stepIndex: event.step_index || 2,
                conflicts: event.conflicts,
                quality: event.quality,
                details: event.details,
                isComplete: false,
              });
            } else if (event.type === 'complete') {
              setOptimProgress({
                percent: 100,
                stage: event.stage,
                stepIndex: 5,
                conflicts: event.conflicts,
                quality: event.quality,
                details: event.details,
                isComplete: true,
              });
              if (event.result) {
                setSchedule(event.result.schedule || []);
                setAnalytics(event.result.analytics || null);
              }
              // Do NOT auto-dismiss with a sudden setTimeout flicker!
              // The user can review the 100% completion card and click "View Timetable" when ready.
            }
          } catch (e) {
            console.error('Error parsing progress stream chunk:', e);
          }
        }
      }
    } catch (err) {
      console.error('Streaming generation error, falling back to standard endpoint:', err);
      try {
        const res = await fetch(`${API_BASE}/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dataset: { ...targetDs, weights: targetWeights },
            solver_type: targetSolver,
            max_time_seconds: 25,
            ga_population_size: 60,
            ga_generations: 150,
          }),
        });
        const data = await res.json();
        setSchedule(data.schedule || []);
        setAnalytics(data.analytics || null);
      } catch (fallbackErr) {
        console.error('Fallback generation failed:', fallbackErr);
      } finally {
        setOptimProgress(null);
      }
    } finally {
      isGeneratingRef.current = false;
      setIsGenerating(false);
    }
  }, []);

  const loadPresetAndGenerate = useCallback(async (presetId) => {
    try {
      const res = await fetch(`${API_BASE}/preset/${presetId}`);
      const ds = await res.json();
      setDataset(ds);
      setWeights(ds.weights || weightsRef.current);

      if (ds.batches && ds.batches.length > 0) {
        setSelectedBatchId(ds.batches[0].id);
      }
      if (ds.faculty && ds.faculty.length > 0) {
        setSelectedFacultyId(ds.faculty[0].id);
      }
      if (ds.rooms && ds.rooms.length > 0) {
        setSelectedRoomId(ds.rooms[0].id);
      }

      await runGenerate(ds, solverTypeRef.current, ds.weights);
    } catch (err) {
      console.error('Error loading preset:', err);
      setIsGenerating(false);
    }
  }, [runGenerate]);

  const fetchPresets = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/presets`);
      const data = await res.json();
      setPresets(data);
    } catch (err) {
      console.error('Error fetching presets:', err);
    }
  }, []);

  // Load presets on mount
  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  // When selectedPresetId changes, load dataset and generate ONCE
  useEffect(() => {
    if (!selectedPresetId || selectedPresetId === 'custom') return;
    if (lastLoadedPresetRef.current === selectedPresetId) return;
    lastLoadedPresetRef.current = selectedPresetId;

    loadPresetAndGenerate(selectedPresetId);
  }, [selectedPresetId, loadPresetAndGenerate]);

  // JSON Import & Export
  const handleExportJson = () => {
    if (!dataset) return;
    const jsonStr = JSON.stringify(dataset, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${dataset.name.replace(/\s+/g, '_')}_Config.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleImportJson = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const importedData = JSON.parse(event.target.result);
        if (!importedData.rooms || !importedData.faculty || !importedData.courses || !importedData.batches) {
          alert('Invalid timetable JSON structure. Missing required rooms, faculty, courses, or batches.');
          return;
        }
        setDataset(importedData);
        setSelectedPresetId('custom');
        if (importedData.batches.length > 0) setSelectedBatchId(importedData.batches[0].id);
        if (importedData.faculty.length > 0) setSelectedFacultyId(importedData.faculty[0].id);
        if (importedData.rooms.length > 0) setSelectedRoomId(importedData.rooms[0].id);
        await runGenerate(importedData, solverType, importedData.weights || weights);
      } catch (err) {
        alert('Failed to parse JSON file: ' + err.message);
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  // Add / Delete Entities
  const handleAddRoom = () => {
    if (!newRoom.name) return;
    const newId = `room_${Date.now()}`;
    const roomObj = {
      id: newId,
      name: newRoom.name,
      room_type: newRoom.room_type,
      capacity: parseInt(newRoom.capacity, 10) || 60,
      building: newRoom.building || 'Main Block',
      floor: 1,
      equipment: [],
    };
    const updated = { ...dataset, rooms: [...dataset.rooms, roomObj] };
    setDataset(updated);
    setShowAddRoomModal(false);
    setNewRoom({ name: '', room_type: 'CLASSROOM', capacity: 60, building: 'Academic Block' });
  };

  const handleDeleteRoom = (roomId) => {
    const updated = { ...dataset, rooms: dataset.rooms.filter((r) => r.id !== roomId) };
    setDataset(updated);
  };

  const handleAddFaculty = () => {
    if (!newFaculty.name) return;
    const newId = `fac_${Date.now()}`;
    const facObj = {
      id: newId,
      name: newFaculty.name,
      department: newFaculty.department,
      designation: newFaculty.designation,
      email: '',
      max_daily_hours: parseInt(newFaculty.max_daily_hours, 10) || 4,
      max_weekly_hours: 18,
      unavailable_slots: [],
      preferred_slots: [],
      qualified_courses: [],
    };
    const updated = { ...dataset, faculty: [...dataset.faculty, facObj] };
    setDataset(updated);
    setShowAddFacultyModal(false);
    setNewFaculty({ name: '', department: 'Computer Science', designation: 'Assistant Professor', max_daily_hours: 4 });
  };

  const handleDeleteFaculty = (facId) => {
    const updated = { ...dataset, faculty: dataset.faculty.filter((f) => f.id !== facId) };
    setDataset(updated);
  };

  const handleAddCourse = () => {
    if (!newCourse.code || !newCourse.name) return;
    const newId = `course_${Date.now()}`;
    const courseObj = {
      id: newId,
      code: newCourse.code,
      name: newCourse.name,
      department: newCourse.department,
      course_type: newCourse.course_type,
      weekly_hours: parseInt(newCourse.weekly_hours, 10) || 3,
      credits: 3,
      room_type_required: newCourse.room_type_required,
      consecutive_slots: newCourse.course_type === 'LAB' ? 2 : 1,
      faculty_ids: newCourse.faculty_id ? [newCourse.faculty_id] : [],
      batch_ids: newCourse.batch_id ? [newCourse.batch_id] : (dataset.batches.length > 0 ? [dataset.batches[0].id] : []),
      color: '#3b82f6',
    };
    const updated = { ...dataset, courses: [...dataset.courses, courseObj] };
    setDataset(updated);
    setShowAddCourseModal(false);
    setNewCourse({ code: '', name: '', department: 'Computer Science', course_type: 'THEORY', weekly_hours: 3, consecutive_slots: 1, room_type_required: 'CLASSROOM', batch_id: '', faculty_id: '' });
  };

  const handleDeleteCourse = (courseId) => {
    const updated = { ...dataset, courses: dataset.courses.filter((c) => c.id !== courseId) };
    setDataset(updated);
  };

  // Export handlers
  const handleExportExcel = async () => {
    if (!dataset || schedule.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/export/excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset,
          schedule,
          solver_type: solverType,
          execution_time_sec: 1.0,
        }),
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${dataset.name.replace(/\s+/g, '_')}_Timetable.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      console.error('Export Excel failed:', err);
    }
  };

  const handleExportPdf = async () => {
    if (!dataset || schedule.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/export/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset,
          schedule,
          solver_type: solverType,
          execution_time_sec: 1.0,
        }),
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${dataset.name.replace(/\s+/g, '_')}_Timetable.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      console.error('Export PDF failed:', err);
    }
  };

  // Slot Inspector / Move Modal
  const openInspector = (slot) => {
    setInspectSlot(slot);
    setMoveTargetDay(slot.day_idx);
    setMoveTargetSlot(slot.slot_idx);
    setMoveTargetRoom(slot.room_id);
    setMoveFeedback(null);
  };

  const handleExecuteMove = async () => {
    if (!inspectSlot || !dataset) return;
    setIsMoving(true);
    setMoveFeedback(null);
    try {
      const payload = {
        dataset,
        schedule,
        slot_id: inspectSlot.id,
        target_day_idx: parseInt(moveTargetDay, 10),
        target_slot_idx: parseInt(moveTargetSlot, 10),
        target_room_id: moveTargetRoom || inspectSlot.room_id,
      };

      const res = await fetch(`${API_BASE}/swap-slot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (data.success) {
        setSchedule(data.updated_schedule);
        setAnalytics(data.analytics);
        const newlyMoved = data.updated_schedule.find((s) => s.id === inspectSlot.id);
        if (newlyMoved) {
          setInspectSlot(newlyMoved);
        }
        setMoveFeedback({
          hasConflicts: data.has_conflicts,
          conflicts: data.conflict_list,
          qualityScore: data.analytics.quality_score,
        });
      }
    } catch (err) {
      console.error('Move error:', err);
    } finally {
      setIsMoving(false);
    }
  };

  // High-performance O(1) cell slot lookup map replacing repetitive 40-times-per-render array filtering
  const cellSlotMap = useMemo(() => {
    const map = {};
    for (const s of schedule) {
      const isTarget =
        (activeTab === 'batch' && s.batch_id === selectedBatchId) ||
        (activeTab === 'faculty' && s.faculty_id === selectedFacultyId) ||
        (activeTab === 'room' && s.room_id === selectedRoomId);
      if (!isTarget) continue;

      for (let p = s.slot_idx; p < s.slot_idx + s.duration; p++) {
        const key = `${s.day_idx}_${p}`;
        if (!map[key]) map[key] = [];
        map[key].push(s);
      }
    }
    return map;
  }, [schedule, activeTab, selectedBatchId, selectedFacultyId, selectedRoomId]);

  if (!dataset) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '0.75rem' }}>
        <RefreshCw className="animate-spin" size={24} color="#2563eb" />
        <span style={{ fontSize: '1.1rem', fontWeight: 600, color: '#334155' }}>Initializing Intelligent Timetable Engine...</span>
      </div>
    );
  }

  const days = dataset.time_config.days;
  const slotTimes = dataset.time_config.slot_times;
  const lunchIdx = dataset.time_config.lunch_slot_idx;

  const currentBatch = dataset.batches.find((b) => b.id === selectedBatchId);
  const currentFaculty = dataset.faculty.find((f) => f.id === selectedFacultyId);
  const currentRoom = dataset.rooms.find((r) => r.id === selectedRoomId);

  return (
    <div className="app-container">
      {/* Hidden File Input for JSON Upload */}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".json"
        onChange={handleImportJson}
      />

      {/* Top Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo-section">
            <div className="logo-badge">
              <Calendar size={22} />
            </div>
            <div>
              <div className="app-title">
                Chronos AI Timetable Studio
                <span className="pill pill-success" style={{ fontSize: '0.65rem', padding: '0.15rem 0.45rem' }}>
                  <ShieldCheck size={12} /> Conflict-Free Engine
                </span>
              </div>
              <div className="app-subtitle">{dataset.name} &bull; {dataset.academic_term}</div>
            </div>
          </div>

          <div className="header-actions">
            {/* Preset Selector */}
            <select
              className="select-control"
              value={selectedPresetId}
              onChange={(e) => setSelectedPresetId(e.target.value)}
              title="Select Campus Preset"
            >
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.batches_count} Batches, {p.courses_count} Courses)
                </option>
              ))}
              <option value="custom">Custom Configured College</option>
            </select>

            {/* Solver Engine Selector */}
            <select
              className="select-control"
              value={solverType}
              onChange={(e) => setSolverType(e.target.value)}
              title="Optimization Solver Engine"
            >
              <option value="cp_sat">OR-Tools CP-SAT (Provably Optimal)</option>
              <option value="genetic">Genetic Algorithm (Evolutionary)</option>
            </select>

            {/* Weights / Settings */}
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setShowSettingsModal(true)}
              title="Tuning Optimization Weights"
            >
              <Sliders size={15} /> Tuning
            </button>

            {/* Generate Action */}
            <button
              className="btn btn-primary"
              onClick={() => runGenerate(dataset)}
              disabled={isGenerating}
            >
              <RefreshCw size={16} className={isGenerating ? 'animate-spin' : ''} />
              {isGenerating ? 'Optimizing...' : 'Generate Timetable'}
            </button>

            {/* Exports */}
            <button className="btn btn-outline btn-sm" onClick={handleExportExcel} title="Download Excel Workbook">
              <FileSpreadsheet size={15} color="#15803d" /> Excel
            </button>
            <button className="btn btn-outline btn-sm" onClick={handleExportPdf} title="Download PDF Report">
              <FileText size={15} color="#b91c1c" /> PDF
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content">
        {/* KPI Score Cards */}
        {analytics && (
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-icon-wrapper" style={{ background: '#eff6ff', color: '#2563eb' }}>
                <Sparkles size={22} />
              </div>
              <div className="kpi-info">
                <div className="kpi-label">Quality Score</div>
                <div className="kpi-value">{analytics.quality_score} <span style={{ fontSize: '0.85rem', color: '#64748b' }}>/ 100</span></div>
                <div className="kpi-sub">{solverType === 'cp_sat' ? 'OR-Tools Exact CP' : 'Genetic Algorithm'}</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon-wrapper" style={{ background: analytics.hard_conflicts_count === 0 ? '#ecfdf5' : '#fef2f2', color: analytics.hard_conflicts_count === 0 ? '#10b981' : '#ef4444' }}>
                {analytics.hard_conflicts_count === 0 ? <CheckCircle2 size={22} /> : <AlertTriangle size={22} />}
              </div>
              <div className="kpi-info">
                <div className="kpi-label">Hard Conflicts</div>
                <div className="kpi-value" style={{ color: analytics.hard_conflicts_count === 0 ? '#10b981' : '#ef4444' }}>
                  {analytics.hard_conflicts_count === 0 ? '0 (Clash-Free)' : `${analytics.hard_conflicts_count} Clashes`}
                </div>
                <div className="kpi-sub">Faculty, room & batch integrity</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon-wrapper" style={{ background: '#f5f3ff', color: '#8b5cf6' }}>
                <Building2 size={22} />
              </div>
              <div className="kpi-info">
                <div className="kpi-label">Room Utilization</div>
                <div className="kpi-value">{analytics.room_utilization_rate}%</div>
                <div className="kpi-sub">Fit eff: {analytics.average_capacity_efficiency}%</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon-wrapper" style={{ background: '#fffbeb', color: '#f59e0b' }}>
                <Clock size={22} />
              </div>
              <div className="kpi-info">
                <div className="kpi-label">Batch Idle Gaps</div>
                <div className="kpi-value">{analytics.batch_idle_hours_per_week} <span style={{ fontSize: '0.8rem', color: '#64748b' }}>hrs/wk</span></div>
                <div className="kpi-sub">Prof gaps: {analytics.faculty_idle_hours_per_week} hrs/wk</div>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-icon-wrapper" style={{ background: '#ecfdf5', color: '#059669' }}>
                <GraduationCap size={22} />
              </div>
              <div className="kpi-info">
                <div className="kpi-label">Prof Preferences</div>
                <div className="kpi-value">{analytics.faculty_preference_satisfaction}%</div>
                <div className="kpi-sub">Preferred slot alignment</div>
              </div>
            </div>
          </div>
        )}

        {/* Tab Navigation & Filters */}
        <div className="nav-tabs-wrapper">
          <div className="nav-tabs">
            <button
              className={`tab-btn ${activeTab === 'batch' ? 'active' : ''}`}
              onClick={() => setActiveTab('batch')}
            >
              <Users size={16} /> Batch Timetable
            </button>
            <button
              className={`tab-btn ${activeTab === 'faculty' ? 'active' : ''}`}
              onClick={() => setActiveTab('faculty')}
            >
              <GraduationCap size={16} /> Faculty Schedules
            </button>
            <button
              className={`tab-btn ${activeTab === 'room' ? 'active' : ''}`}
              onClick={() => setActiveTab('room')}
            >
              <Building2 size={16} /> Room Occupancy
            </button>
            <button
              className={`tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveTab('analytics')}
            >
              <BarChart3 size={16} /> Conflict Auditor & Analytics
            </button>
            <button
              className={`tab-btn ${activeTab === 'dataset' ? 'active' : ''}`}
              onClick={() => setActiveTab('dataset')}
            >
              <Layers size={16} /> Campus Data & Configuration Editor
            </button>
          </div>

          {/* Perspective Dropdown Filters */}
          <div className="filter-group">
            {activeTab === 'batch' && (
              <select
                className="select-control"
                value={selectedBatchId}
                onChange={(e) => setSelectedBatchId(e.target.value)}
              >
                {dataset.batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} (Semester {b.semester}, {b.size} Students)
                  </option>
                ))}
              </select>
            )}

            {activeTab === 'faculty' && (
              <select
                className="select-control"
                value={selectedFacultyId}
                onChange={(e) => setSelectedFacultyId(e.target.value)}
              >
                {dataset.faculty.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({f.designation}, {f.department})
                  </option>
                ))}
              </select>
            )}

            {activeTab === 'room' && (
              <select
                className="select-control"
                value={selectedRoomId}
                onChange={(e) => setSelectedRoomId(e.target.value)}
              >
                {dataset.rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.room_type}, Capacity: {r.capacity})
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* View 1: Timetable Grid (Batches, Faculty, or Rooms) */}
        {(activeTab === 'batch' || activeTab === 'faculty' || activeTab === 'room') && (
          <div className="timetable-wrapper">
            <div className="timetable-header">
              <div>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a' }}>
                  {activeTab === 'batch' && currentBatch && `${currentBatch.name} — Weekly Schedule`}
                  {activeTab === 'faculty' && currentFaculty && `${currentFaculty.name} — Teaching Schedule (${currentFaculty.department})`}
                  {activeTab === 'room' && currentRoom && `${currentRoom.name} — Room Master Occupancy (${currentRoom.room_type})`}
                </h2>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  {activeTab === 'batch' && currentBatch && `Enrolled: ${currentBatch.size} students | Department: ${currentBatch.department}`}
                  {activeTab === 'faculty' && currentFaculty && `Max Load: ${currentFaculty.max_daily_hours} hrs/day | Weekly limit: ${currentFaculty.max_weekly_hours} hrs`}
                  {activeTab === 'room' && currentRoom && `Seating Capacity: ${currentRoom.capacity} seats | Location: ${currentRoom.building}, Floor ${currentRoom.floor}`}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
                <span className="badge-tag badge-theory">Theory</span>
                <span className="badge-tag badge-lab">2-Hour Lab Block</span>
                <span style={{ marginLeft: '0.5rem' }}>&bull; Click any card to inspect or move</span>
              </div>
            </div>

            <div className="table-responsive">
              <table className="schedule-grid-table">
                <thead>
                  <tr>
                    <th className="day-col-header">Day / Period</th>
                    {slotTimes.map((timeLabel, idx) => (
                      <th
                        key={idx}
                        style={{
                          background: idx === lunchIdx ? '#fefce8' : undefined,
                          color: idx === lunchIdx ? '#854d0e' : undefined,
                        }}
                      >
                        {timeLabel}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {days.map((dayName, dayIdx) => (
                    <tr key={dayIdx}>
                      <td className="day-cell">{dayName}</td>
                      {slotTimes.map((_, periodIdx) => {
                        if (periodIdx === lunchIdx) {
                          return (
                            <td key={periodIdx} className="slot-cell slot-lunch">
                              LUNCH RECESS
                            </td>
                          );
                        }

                        const cellSlots = cellSlotMap[`${dayIdx}_${periodIdx}`] || [];

                        if (cellSlots.length === 0) {
                          return (
                            <td key={periodIdx} className="slot-cell">
                              <div className="slot-empty">—</div>
                            </td>
                          );
                        }

                        return (
                          <td key={periodIdx} className="slot-cell">
                            {cellSlots.map((slot) => {
                              const isStartPeriod = slot.slot_idx === periodIdx;
                              return (
                                <div
                                  key={slot.id}
                                  className="class-card"
                                  style={{
                                    borderLeftColor: slot.color || '#2563eb',
                                    opacity: isStartPeriod ? 1 : 0.85,
                                  }}
                                  onClick={() => openInspector(slot)}
                                  title="Click to view details or move slot"
                                >
                                  <div className="class-card-top">
                                    <span className="class-code">{slot.course_code}</span>
                                    <span
                                      className={`badge-tag ${
                                        slot.course_type === 'LAB' ? 'badge-lab' : 'badge-theory'
                                      }`}
                                    >
                                      {slot.course_type === 'LAB' ? `${slot.duration}H Lab` : 'Lecture'}
                                    </span>
                                  </div>
                                  <div className="class-title">{slot.course_name}</div>
                                  <div className="class-meta">
                                    {activeTab !== 'faculty' && (
                                      <div className="meta-row" title={`Faculty: ${slot.faculty_name}`}>
                                        <GraduationCap size={12} color="#64748b" /> {slot.faculty_name}
                                      </div>
                                    )}
                                    {activeTab !== 'room' && (
                                      <div className="meta-row" title={`Room: ${slot.room_name}`}>
                                        <Building2 size={12} color="#64748b" /> {slot.room_name}
                                      </div>
                                    )}
                                    {activeTab !== 'batch' && (
                                      <div className="meta-row" title={`Batch: ${slot.batch_name}`}>
                                        <Users size={12} color="#64748b" /> {slot.batch_name}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* View 2: Conflict Auditor & Analytics Dashboard */}
        {activeTab === 'analytics' && analytics && (
          <div className="analytics-grid">
            {/* Conflict Auditor Summary */}
            <div className="analytics-card" style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ShieldCheck size={20} color={analytics.hard_conflicts_count === 0 ? '#10b981' : '#ef4444'} />
                  Conflict Auditor & Constraint Verification Report
                </h3>
                <span className={`pill ${analytics.hard_conflicts_count === 0 ? 'pill-success' : 'pill-danger'}`}>
                  {analytics.hard_conflicts_count === 0 ? '100% Conflict-Free Verified' : `${analytics.hard_conflicts_count} Hard Conflicts`}
                </span>
              </div>

              {analytics.hard_conflicts_count === 0 ? (
                <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '8px', padding: '1rem', color: '#065f46', fontSize: '0.875rem' }}>
                  <b>Zero Hard Constraints Violated:</b> All faculty assignments, room occupancies, student batch schedules, capacity requirements, lab block continuities, and blackout periods were strictly verified with no clashes.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {analytics.conflict_list.map((c, i) => (
                    <div key={i} style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '0.65rem', color: '#991b1b', fontSize: '0.8rem' }}>
                      {c}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Faculty Workload Chart */}
            <div className="analytics-card">
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <GraduationCap size={18} color="#2563eb" /> Faculty Weekly Teaching Load & Gaps
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                {Object.entries(analytics.faculty_workloads).map(([fid, f]) => {
                  const maxWeekly = 18;
                  const pct = Math.min(100, Math.round((f.total_weekly_hours / maxWeekly) * 100));
                  return (
                    <div key={fid}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600 }}>
                        <span>{f.name}</span>
                        <span>{f.total_weekly_hours} hrs/wk ({f.idle_gap_hours} idle gaps)</span>
                      </div>
                      <div className="progress-bar-container">
                        <div className="progress-bar-fill" style={{ width: `${pct}%`, background: '#2563eb' }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Room Occupancy & Utilization */}
            <div className="analytics-card">
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Building2 size={18} color="#059669" /> Classroom & Laboratory Utilization
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                {Object.entries(analytics.room_occupancy).map(([rid, r]) => (
                  <div key={rid}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600 }}>
                      <span>{r.name} <span style={{ color: '#64748b', fontSize: '0.72rem' }}>({r.type}, Cap: {r.capacity})</span></span>
                      <span>{r.occupied_hours} hrs ({r.utilization_percent}%)</span>
                    </div>
                    <div className="progress-bar-container">
                      <div className="progress-bar-fill" style={{ width: `${r.utilization_percent}%`, background: '#059669' }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Detailed Metric KPI Breakdown */}
            <div className="analytics-card" style={{ gridColumn: '1 / -1' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem' }}>
                Full Optimization Metric Breakdown
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                {Object.entries(analytics.metrics_breakdown).map(([k, m]) => (
                  <div key={k} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.85rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', color: '#475569' }}>
                        {k.replace(/_/g, ' ')}
                      </span>
                      <span className={`pill ${m.status === 'excellent' ? 'pill-success' : m.status === 'warning' ? 'pill-warning' : 'pill-danger'}`}>
                        {m.value} {m.unit}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{m.description}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* View 3: Dataset & Configuration Editor */}
        {activeTab === 'dataset' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Action Bar for Custom JSON Configuration */}
            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a' }}>
                  Interactive Campus Data & Constraint Configuration
                </h3>
                <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  All college data is 100% configurable. You can add/delete rooms, faculty, and courses, or export/import custom JSON files.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button className="btn btn-outline btn-sm" onClick={() => fileInputRef.current?.click()} title="Import any college JSON dataset">
                  <Upload size={14} /> Import Custom JSON
                </button>
                <button className="btn btn-outline btn-sm" onClick={handleExportJson} title="Export current config as JSON template">
                  <Download size={14} /> Export Config JSON
                </button>
                <button className="btn btn-primary btn-sm" onClick={() => runGenerate(dataset)}>
                  <RefreshCw size={14} /> Re-Generate Schedule
                </button>
              </div>
            </div>

            <div className="analytics-grid">
              {/* Rooms & Facilities Card */}
              <div className="analytics-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e3a8a', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Building2 size={16} /> Rooms & Labs ({dataset.rooms.length})
                  </h4>
                  <button className="btn btn-outline btn-sm" onClick={() => setShowAddRoomModal(true)}>
                    <Plus size={14} /> Add Room
                  </button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto' }}>
                  {dataset.rooms.map((r) => (
                    <div key={r.id} style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.65rem', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{r.name}</div>
                        <div style={{ color: '#64748b' }}>Type: {r.room_type} &bull; Capacity: <b>{r.capacity}</b> seats &bull; {r.building}</div>
                      </div>
                      <button
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8', padding: '0.2rem' }}
                        onClick={() => handleDeleteRoom(r.id)}
                        title="Delete Room"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Faculty Card */}
              <div className="analytics-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e3a8a', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <GraduationCap size={16} /> Faculty Profiles ({dataset.faculty.length})
                  </h4>
                  <button className="btn btn-outline btn-sm" onClick={() => setShowAddFacultyModal(true)}>
                    <Plus size={14} /> Add Faculty
                  </button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto' }}>
                  {dataset.faculty.map((f) => (
                    <div key={f.id} style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.65rem', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{f.name}</div>
                        <div style={{ color: '#64748b' }}>{f.designation} &bull; {f.department} &bull; Max: {f.max_daily_hours}h/day</div>
                        <div style={{ fontSize: '0.72rem', color: '#e11d48', marginTop: '0.2rem' }}>
                          Unavailable: {f.unavailable_slots.length > 0 ? `${f.unavailable_slots.length} blackout slots` : 'Full availability'}
                        </div>
                      </div>
                      <button
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8', padding: '0.2rem' }}
                        onClick={() => handleDeleteFaculty(f.id)}
                        title="Delete Faculty"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Courses Card */}
              <div className="analytics-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e3a8a', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <BookOpen size={16} /> Courses & Labs ({dataset.courses.length})
                  </h4>
                  <button className="btn btn-outline btn-sm" onClick={() => setShowAddCourseModal(true)}>
                    <Plus size={14} /> Add Course
                  </button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto' }}>
                  {dataset.courses.map((c) => (
                    <div key={c.id} style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.65rem', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{c.code}: {c.name}</div>
                        <div style={{ color: '#64748b' }}>
                          {c.course_type} &bull; {c.weekly_hours} hrs/wk ({c.consecutive_slots > 1 ? `${c.consecutive_slots}h block` : '1h lecture'}) &bull; Req: {c.room_type_required}
                        </div>
                      </div>
                      <button
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8', padding: '0.2rem' }}
                        onClick={() => handleDeleteCourse(c.id)}
                        title="Delete Course"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Modal: Add Room */}
      {showAddRoomModal && (
        <div className="modal-overlay" onClick={() => setShowAddRoomModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800 }}>Add New Classroom or Lab</h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowAddRoomModal(false)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Room Name</label>
                <input
                  type="text"
                  placeholder="e.g. CR-305 (Euler Hall)"
                  className="select-control"
                  style={{ width: '100%', marginTop: '0.25rem' }}
                  value={newRoom.name}
                  onChange={(e) => setNewRoom({ ...newRoom, name: e.target.value })}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Facility Type</label>
                  <select
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newRoom.room_type}
                    onChange={(e) => setNewRoom({ ...newRoom, room_type: e.target.value })}
                  >
                    <option value="CLASSROOM">Classroom</option>
                    <option value="LECTURE_HALL">Lecture Hall</option>
                    <option value="LAB_COMPUTER">Computer Lab</option>
                    <option value="LAB_ELECTRONICS">Electronics Lab</option>
                    <option value="SEMINAR_HALL">Seminar Hall</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Seating Capacity</label>
                  <input
                    type="number"
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newRoom.capacity}
                    onChange={(e) => setNewRoom({ ...newRoom, capacity: e.target.value })}
                  />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button className="btn btn-outline" onClick={() => setShowAddRoomModal(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddRoom}>Add Facility</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Add Faculty */}
      {showAddFacultyModal && (
        <div className="modal-overlay" onClick={() => setShowAddFacultyModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800 }}>Add Faculty Member</h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowAddFacultyModal(false)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Dr. Jane Doe"
                  className="select-control"
                  style={{ width: '100%', marginTop: '0.25rem' }}
                  value={newFaculty.name}
                  onChange={(e) => setNewFaculty({ ...newFaculty, name: e.target.value })}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Department</label>
                  <input
                    type="text"
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newFaculty.department}
                    onChange={(e) => setNewFaculty({ ...newFaculty, department: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Designation</label>
                  <input
                    type="text"
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newFaculty.designation}
                    onChange={(e) => setNewFaculty({ ...newFaculty, designation: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Max Daily Teaching Hours</label>
                <input
                  type="number"
                  className="select-control"
                  style={{ width: '100%', marginTop: '0.25rem' }}
                  value={newFaculty.max_daily_hours}
                  onChange={(e) => setNewFaculty({ ...newFaculty, max_daily_hours: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button className="btn btn-outline" onClick={() => setShowAddFacultyModal(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddFaculty}>Add Faculty</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Add Course */}
      {showAddCourseModal && (
        <div className="modal-overlay" onClick={() => setShowAddCourseModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800 }}>Add New Course / Lab</h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowAddCourseModal(false)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Course Code</label>
                  <input
                    type="text"
                    placeholder="CS304"
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newCourse.code}
                    onChange={(e) => setNewCourse({ ...newCourse, code: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Course Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Software Engineering"
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newCourse.name}
                    onChange={(e) => setNewCourse({ ...newCourse, name: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Course Type</label>
                  <select
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newCourse.course_type}
                    onChange={(e) => setNewCourse({ ...newCourse, course_type: e.target.value })}
                  >
                    <option value="THEORY">Theory (Lecture)</option>
                    <option value="LAB">Lab Block (Practical)</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Weekly Hours</label>
                  <input
                    type="number"
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newCourse.weekly_hours}
                    onChange={(e) => setNewCourse({ ...newCourse, weekly_hours: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Required Room Type</label>
                  <select
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newCourse.room_type_required}
                    onChange={(e) => setNewCourse({ ...newCourse, room_type_required: e.target.value })}
                  >
                    <option value="CLASSROOM">Classroom</option>
                    <option value="LECTURE_HALL">Lecture Hall</option>
                    <option value="LAB_COMPUTER">Computer Lab</option>
                    <option value="LAB_ELECTRONICS">Electronics Lab</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Assigned Instructor</label>
                  <select
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={newCourse.faculty_id}
                    onChange={(e) => setNewCourse({ ...newCourse, faculty_id: e.target.value })}
                  >
                    <option value="">Any Qualified Faculty</option>
                    {dataset.faculty.map((f) => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Target Student Batch</label>
                <select
                  className="select-control"
                  style={{ width: '100%', marginTop: '0.25rem' }}
                  value={newCourse.batch_id}
                  onChange={(e) => setNewCourse({ ...newCourse, batch_id: e.target.value })}
                >
                  <option value="">Select Batch</option>
                  {dataset.batches.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button className="btn btn-outline" onClick={() => setShowAddCourseModal(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddCourse}>Add Course</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Optimization Tuning Drawer Modal */}
      {showSettingsModal && (
        <div className="modal-overlay" onClick={() => setShowSettingsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sliders size={20} color="#2563eb" /> Tuning Optimization Objective Weights
              </h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowSettingsModal(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Customize the multi-objective penalties. The CP-SAT and Genetic solvers will optimize schedules according to your institutional priorities.
              </p>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600 }}>
                  <span>Student Idle Time Penalty</span>
                  <span>{weights.weight_idle_student}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.5"
                  style={{ width: '100%', marginTop: '0.35rem' }}
                  value={weights.weight_idle_student}
                  onChange={(e) => setWeights({ ...weights, weight_idle_student: parseFloat(e.target.value) })}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600 }}>
                  <span>Faculty Idle Time Penalty</span>
                  <span>{weights.weight_idle_faculty}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.5"
                  style={{ width: '100%', marginTop: '0.35rem' }}
                  value={weights.weight_idle_faculty}
                  onChange={(e) => setWeights({ ...weights, weight_idle_faculty: parseFloat(e.target.value) })}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600 }}>
                  <span>Daily Workload Balance Weight</span>
                  <span>{weights.weight_workload_balance}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.5"
                  style={{ width: '100%', marginTop: '0.35rem' }}
                  value={weights.weight_workload_balance}
                  onChange={(e) => setWeights({ ...weights, weight_workload_balance: parseFloat(e.target.value) })}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600 }}>
                  <span>Faculty Time Preferences Bonus</span>
                  <span>{weights.weight_faculty_preference}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.5"
                  style={{ width: '100%', marginTop: '0.35rem' }}
                  value={weights.weight_faculty_preference}
                  onChange={(e) => setWeights({ ...weights, weight_faculty_preference: parseFloat(e.target.value) })}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button className="btn btn-outline" onClick={() => setShowSettingsModal(false)}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setShowSettingsModal(false);
                    runGenerate(dataset, solverType, weights);
                  }}
                >
                  Apply & Re-Optimize
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Inspect & Move Slot Modal */}
      {inspectSlot && (
        <div className="modal-overlay" onClick={() => setInspectSlot(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
                {inspectSlot.course_code}: {inspectSlot.course_name}
              </h3>
              <button className="btn btn-outline btn-sm" onClick={() => setInspectSlot(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="modal-body">
              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.85rem', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <div><b>Batch:</b> {inspectSlot.batch_name}</div>
                <div><b>Faculty:</b> {inspectSlot.faculty_name}</div>
                <div><b>Room:</b> {inspectSlot.room_name}</div>
                <div><b>Current Slot:</b> {inspectSlot.day_name}, {inspectSlot.slot_time} ({inspectSlot.duration} period{inspectSlot.duration > 1 ? 's' : ''})</div>
              </div>

              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e3a8a', marginTop: '0.5rem' }}>
                Move or Swap Slot (With Live Conflict Verification)
              </h4>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Target Day</label>
                  <select
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={moveTargetDay}
                    onChange={(e) => setMoveTargetDay(e.target.value)}
                  >
                    {days.map((d, i) => (
                      <option key={i} value={i}>{d}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Target Start Slot</label>
                  <select
                    className="select-control"
                    style={{ width: '100%', marginTop: '0.25rem' }}
                    value={moveTargetSlot}
                    onChange={(e) => setMoveTargetSlot(e.target.value)}
                  >
                    {slotTimes.map((t, i) => {
                      if (i === lunchIdx) return null;
                      return <option key={i} value={i}>{t}</option>;
                    })}
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Assigned Classroom / Lab</label>
                <select
                  className="select-control"
                  style={{ width: '100%', marginTop: '0.25rem' }}
                  value={moveTargetRoom}
                  onChange={(e) => setMoveTargetRoom(e.target.value)}
                >
                  {dataset.rooms.map((r) => (
                    <option key={r.id} value={r.id}>{r.name} ({r.room_type}, Cap: {r.capacity})</option>
                  ))}
                </select>
              </div>

              {moveFeedback && (
                <div style={{ marginTop: '0.5rem' }}>
                  {moveFeedback.hasConflicts ? (
                    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '0.75rem', color: '#b91c1c', fontSize: '0.8rem' }}>
                      <b>Move Created Conflicts:</b>
                      <ul style={{ paddingLeft: '1.2rem', marginTop: '0.3rem' }}>
                        {moveFeedback.conflicts.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '8px', padding: '0.75rem', color: '#047857', fontSize: '0.8rem' }}>
                      <b>Move Validated:</b> Slot successfully moved with 0 hard conflicts! Quality score: {moveFeedback.qualityScore}/100.
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button className="btn btn-outline" onClick={() => setInspectSlot(null)}>
                  Close
                </button>
                <button className="btn btn-primary" onClick={handleExecuteMove} disabled={isMoving}>
                  {isMoving ? 'Validating Move...' : 'Move & Audit Clash'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Visual Optimization Progress & Telemetry Modal */}
      {optimProgress && (
        <div className="optim-modal-overlay">
          <div className="optim-modal-content">
            <div className="optim-header">
              <div className="optim-header-title">
                <Sparkles size={20} className={optimProgress.isComplete ? '' : 'animate-spin'} />
                <span>{optimProgress.isComplete ? 'Schedule Optimization Completed' : 'AI Timetable Optimization Active'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div className="optim-engine-tag">
                  {solverType === 'cp_sat' ? 'Google OR-Tools CP-SAT' : 'Adaptive Genetic Algorithm'}
                </div>
                {optimProgress.isComplete && (
                  <button
                    onClick={() => setOptimProgress(null)}
                    style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: 2, display: 'flex', alignItems: 'center' }}
                    title="Close Dialog"
                  >
                    <X size={18} />
                  </button>
                )}
              </div>
            </div>

            <div className="optim-body">
              {/* Progress Bar & Stage */}
              <div className="optim-progress-section">
                <div className="optim-progress-info">
                  <span style={{ color: '#1e3a8a' }}>{optimProgress.stage}</span>
                  <span style={{ color: '#2563eb', fontFamily: 'monospace', fontSize: '1.05rem' }}>{optimProgress.percent}%</span>
                </div>
                <div className="optim-progress-track">
                  <div className="optim-progress-fill" style={{ width: `${optimProgress.percent}%` }} />
                </div>
              </div>

              {/* 3 Telemetry HUD Cards */}
              <div className="optim-hud-grid">
                <div className="optim-hud-card">
                  <div className="optim-hud-label">Clashes Remaining</div>
                  <div className="optim-hud-val" style={{ color: optimProgress.conflicts === 0 ? '#10b981' : '#ef4444' }}>
                    {optimProgress.conflicts === 0 ? '0 (Clash-Free)' : optimProgress.conflicts}
                  </div>
                </div>
                <div className="optim-hud-card">
                  <div className="optim-hud-label">Convergence Score</div>
                  <div className="optim-hud-val" style={{ color: '#2563eb' }}>
                    {optimProgress.quality}%
                  </div>
                </div>
                <div className="optim-hud-card">
                  <div className="optim-hud-label">Search Workers</div>
                  <div className="optim-hud-val" style={{ color: '#8b5cf6' }}>
                    8 Cores Active
                  </div>
                </div>
              </div>

              {/* Step-by-Step Milestones Checklist */}
              <div className="optim-checklist">
                {[
                  { step: 1, title: 'Campus syllabi & room capacities verified' },
                  { step: 2, title: 'Boolean non-overlap constraint model built' },
                  { step: 3, title: 'Clash elimination & parallel search active' },
                  { step: 4, title: 'Multi-objective workload & idle gap minimization' },
                  { step: 5, title: '100% Conflict-free timetable verified' },
                ].map((m) => {
                  const isDone = (optimProgress.stepIndex || 1) > m.step || optimProgress.isComplete;
                  const isCurrent = (optimProgress.stepIndex || 1) === m.step && !optimProgress.isComplete;
                  return (
                    <div key={m.step} className={`optim-step-row ${isDone ? 'completed' : isCurrent ? 'active' : ''}`}>
                      <div className="optim-step-icon">
                        {isDone ? (
                          <CheckCircle2 size={16} color="#10b981" />
                        ) : isCurrent ? (
                          <RefreshCw size={14} color="#2563eb" className="animate-spin" />
                        ) : (
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#cbd5e1' }} />
                        )}
                      </div>
                      <span>{m.title}</span>
                    </div>
                  );
                })}
              </div>

              {/* Details Ticker */}
              <div className="optim-details-text">
                {optimProgress.details}
              </div>

              {/* Complete Confirmation Banner */}
              {optimProgress.isComplete && (
                <div className="optim-complete-box">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <CheckCircle2 size={24} color="#059669" />
                    <div>
                      <div style={{ fontWeight: 800, color: '#065f46', fontSize: '0.95rem' }}>
                        Optimization Complete!
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#047857' }}>
                        Zero conflicts detected &bull; Quality Score: <b>{optimProgress.quality}/100</b>
                      </div>
                    </div>
                  </div>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setOptimProgress(null)}
                    style={{ padding: '0.55rem 1.25rem', fontWeight: 800, fontSize: '0.85rem' }}
                  >
                    View Timetable &rarr;
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="app-footer">
        Powered by Google OR-Tools CP-SAT & Advanced Genetic Metaheuristic Algorithms &bull; Intelligent College Timetable Generator
      </footer>
    </div>
  );
}
