import React, { useState, useCallback, useMemo, useEffect, createContext } from 'react';

export const VisionChangesContext = createContext({ newIds: new Set(), changedIds: new Set() });
import { useVisionStore } from './useVisionStore.js';
import AppSidebar from './AppSidebar.jsx';
import ItemListView from './ItemListView.jsx';
import BoardView from './BoardView.jsx';
import TreeView from './TreeView.jsx';
import GraphView from './GraphView.jsx';
import RoadmapView from './RoadmapView.jsx';
import DocsView from './DocsView.jsx';
import AttentionView from './AttentionView.jsx';
import ItemDetailPanel from './ItemDetailPanel.jsx';
import ChallengeModal from './ChallengeModal.jsx';

export default function VisionTracker() {
  const {
    items, connections, connected, uiCommand, clearUICommand, recentChanges,
    createItem, updateItem, deleteItem, createConnection, deleteConnection,
    agentActivity, agentErrors, sessionState, registerSnapshotProvider,
  } = useVisionStore();

  const [selectedItemId, setSelectedItemId] = useState(() => sessionStorage.getItem('vision-selectedItemId') || null);
  const [activeView, setActiveView] = useState(() => sessionStorage.getItem('vision-activeView') || 'roadmap');
  const [selectedPhase, setSelectedPhase] = useState(() => sessionStorage.getItem('vision-selectedPhase') || null);
  const [searchQuery, setSearchQuery] = useState('');
  const [challengeItemId, setChallengeItemId] = useState(null);

  // Persist UI state to sessionStorage
  useEffect(() => { sessionStorage.setItem('vision-activeView', activeView); }, [activeView]);
  useEffect(() => {
    if (selectedPhase) sessionStorage.setItem('vision-selectedPhase', selectedPhase);
    else sessionStorage.removeItem('vision-selectedPhase');
  }, [selectedPhase]);
  useEffect(() => {
    if (selectedItemId) sessionStorage.setItem('vision-selectedItemId', selectedItemId);
    else sessionStorage.removeItem('vision-selectedItemId');
  }, [selectedItemId]);

  // UI commands from server
  useEffect(() => {
    if (!uiCommand) return;
    if (uiCommand.view) setActiveView(uiCommand.view);
    if (uiCommand.phase !== undefined) setSelectedPhase(uiCommand.phase);
    if (uiCommand.select !== undefined) setSelectedItemId(uiCommand.select);
    clearUICommand();
  }, [uiCommand, clearUICommand]);

  // Filter items by phase + search
  const filteredItems = useMemo(() => {
    let result = items;
    if (selectedPhase) result = result.filter(i => i.phase === selectedPhase);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(i =>
        i.title.toLowerCase().includes(q) ||
        (i.description || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [items, selectedPhase, searchQuery]);

  // Filter connections to match filtered items
  const filteredConnections = useMemo(() => {
    if (!selectedPhase && !searchQuery) return connections;
    const ids = new Set(filteredItems.map(i => i.id));
    return connections.filter(c => ids.has(c.fromId) && ids.has(c.toId));
  }, [connections, filteredItems, selectedPhase, searchQuery]);

  // Register snapshot provider so the store can capture UI state on demand
  useEffect(() => {
    registerSnapshotProvider(() => ({
      activeView,
      selectedPhase,
      searchQuery,
      selectedItemId,
      totalItems: items.length,
      filteredCount: filteredItems.length,
      connected,
    }));
  }, [registerSnapshotProvider, activeView, selectedPhase, searchQuery, selectedItemId, items.length, filteredItems.length, connected]);

  const handleSelect = useCallback((id) => {
    setSelectedItemId(id);
  }, []);

  const handleUpdate = useCallback((id, data) => {
    updateItem(id, data);
  }, [updateItem]);

  const handleCreate = useCallback(async () => {
    const phase = selectedPhase || 'vision';
    const result = await createItem({
      type: 'task',
      title: 'New item',
      description: '',
      status: 'planned',
      confidence: 0,
      phase,
    });
    if (result && result.id) {
      setSelectedItemId(result.id);
    }
  }, [createItem, selectedPhase]);

  const handleDelete = useCallback(async (id) => {
    await deleteItem(id);
    if (selectedItemId === id) setSelectedItemId(null);
  }, [deleteItem, selectedItemId]);

  const handleCreateConnection = useCallback(async (data) => {
    return createConnection(data);
  }, [createConnection]);

  const handleDeleteConnection = useCallback(async (id) => {
    return deleteConnection(id);
  }, [deleteConnection]);

  const selectedItem = items.find(i => i.id === selectedItemId) || null;

  return (
    <VisionChangesContext.Provider value={recentChanges}>
    <div className="h-full flex bg-background" data-snapshot-root>
      {/* Sidebar */}
      <AppSidebar
        items={items}
        activeView={activeView}
        onViewChange={setActiveView}
        selectedPhase={selectedPhase}
        onPhaseSelect={setSelectedPhase}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        connected={connected}
        agentActivity={agentActivity}
        agentErrors={agentErrors}
        sessionState={sessionState}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Connection warning */}
        {!connected && (
          <div className="text-center text-[10px] py-0.5 bg-destructive text-destructive-foreground">
            Disconnected — reconnecting...
          </div>
        )}

        {/* View content */}
        {activeView === 'roadmap' && (
          <RoadmapView
            items={items}
            connections={connections}
            selectedPhase={selectedPhase}
            onAction={(itemId, action, extra) => {
              if (action === 'approve') handleUpdate(itemId, { status: 'complete' });
              else if (action === 'decline' || action === 'dismiss') handleUpdate(itemId, { status: 'killed' });
              else if (action === 'resolve') {
                const updates = { status: 'complete' };
                if (extra) updates.description = extra;
                handleUpdate(itemId, updates);
              }
              else if (action === 'pressure-test') setChallengeItemId(itemId);
              else if (action === 'discuss') handleSelect(itemId);
            }}
          />
        )}
        {activeView === 'list' && (
          <ItemListView
            items={filteredItems}
            selectedItemId={selectedItemId}
            onSelect={handleSelect}
            onCreate={handleCreate}
          />
        )}
        {activeView === 'board' && (
          <BoardView
            items={filteredItems}
            selectedItemId={selectedItemId}
            onSelect={handleSelect}
            onUpdateStatus={(id, status) => handleUpdate(id, { status })}
          />
        )}
        {activeView === 'tree' && (
          <TreeView
            items={filteredItems}
            connections={filteredConnections}
            selectedItemId={selectedItemId}
            onSelect={handleSelect}
          />
        )}
        {activeView === 'graph' && (
          <GraphView
            items={filteredItems}
            connections={filteredConnections}
            selectedItemId={selectedItemId}
            onSelect={handleSelect}
          />
        )}
        {activeView === 'docs' && (
          <DocsView items={items} />
        )}
        {activeView === 'attention' && (
          <AttentionView
            items={items}
            selectedItemId={selectedItemId}
            onSelect={handleSelect}
          />
        )}
      </div>

      {/* Detail panel */}
      {selectedItem && (
        <ItemDetailPanel
          item={selectedItem}
          items={items}
          connections={connections}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
          onCreateConnection={handleCreateConnection}
          onDeleteConnection={handleDeleteConnection}
          onSelect={handleSelect}
          onClose={() => setSelectedItemId(null)}
          onPressureTest={setChallengeItemId}
        />
      )}

      {/* Challenge modal */}
      {challengeItemId && (() => {
        const challengeItem = items.find(i => i.id === challengeItemId);
        if (!challengeItem) return null;
        return (
          <ChallengeModal
            item={challengeItem}
            items={items}
            connections={connections}
            onUpdate={handleUpdate}
            onClose={() => setChallengeItemId(null)}
          />
        );
      })()}
    </div>
    </VisionChangesContext.Provider>
  );
}
