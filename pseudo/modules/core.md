# `core.py`

OWNS:
  bounded current world / current application state
  Reducer Core
  Core machine runtime
  Core effects processing
  declarative Tk commands
  Core lifecycle

Lifecycle uses the claimed runtime's `running` field. `None` in the Core inbox
becomes `SHUTDOWN`, whose effects stop Core, send Mem its sentinel, and allow
Tk to close. This does not drain outstanding return stacks.

An unloaded panel cannot be renamed. Rename currently changes only the active
Core copy; there is no canonical commit operation in Stage 3.

READS:
  plain Tk semantic events
  Mobile Stacks addressed to CORE

ENSURES:
  the active layout says which panel is hosted where

PSEUDOCODE:


  == Core Loop ==

  receive one inbox item
  translate it into zero or more Reducer events
  process the Reducer event queue until empty
  return to blocking on Core inbox


  == Core machine receives item ==

  if item is Tk semantic event:
      enqueue Reducer event
  
  if item is Mobile Stack:
      inspect top frame
          machine = CORE
          entry = ...
  
      translate:
          stack entry + independent copies of retained register data
              -> ordinary Reducer event
  
      enqueue Reducer event
  
      drop_frame()
  
      if stack has more frames:
          route stack to machine named by new top frame
      else:
          stack is complete/dead


  == After inbound item has been translated ==

  proceed queued Reducer events

  for each Reducer event:

    next_state, effects =
        reduce(current_state, event)

    current_state = next_state

    for each effect:
        dispatch effect


  == Effect dispatch ==

  if effect targets Tk:
      send declarative semantic command
      through Tk's special queue/wakeup path

  if effect requires another machine:
      create Mobile Stack

      set registers
      push appropriate frames
      route stack to target machine


  == Stage 4 hosting ==

  HOST_PANEL(position-id, panel-id)
      -> GET_PANEL through Mem
      -> PANEL_FOR_HOSTING_RECEIVED
      -> position.panel-id = panel-id
      -> targeted hosted-panel command to Tk


  == Stage 7B fixed geometry ==

  tab-a owns ordered row ids
  each row has column-count 1, 2, or 3
  position id = row-id + "/column-" + logical column

  positions[position-id].panel-id may be null
  RENDER_TODAY carries the complete fixed row/position structure


  == Stage 7C canonical hosting ==

  GET_DAY_LAYOUT loads Mem's active layout snapshot into Core
  HOST_PANEL gets the panel, then asks Mem to host it
  UNHOST_PANEL asks Mem to clear only the hosting relation
  Mem's accepted return becomes a targeted RENDER_POSITION command


  == Stage 7D selected tab ==

  SELECT_TAB -> Mem -> accepted selected tab
  -> SET_SELECTED_TAB command to Tk


  == Day navigation ==

  SELECT_PREVIOUS_DAY / SELECT_NEXT_DAY / SELECT_TODAY
  -> request GET_DAY_LAYOUT for the target date

  A pending navigation waits for dirty whiteboards to receive Mem's accepted
  update. The returned day layout replaces Core's active day snapshot.


  == Stage 7E geometry ==

  SET_ROW_HEIGHT and SET_SASH_PROPORTIONS
  -> Mem accepts one row's geometry
  -> Core sends targeted Tk geometry command


  == Stage 7F row movement ==

  MOVE_ROW -> Mem changes tab.row-ids
  -> Core reconciles the structurally changed day workspace

  ADD_ROW -> Mem appends a minted one-column row
  -> Core reconciles the structurally changed day workspace

  DELETE_ROW -> Mem removes a non-final row
  SET_ROW_COLUMN_COUNT -> Mem changes one row's derived position slots

  CREATE_TAB / DELETE_TAB -> Mem changes the day's ordered tab ids
  RENAME_TAB -> Mem accepts a label; Core sends one targeted tab-label command

  SET_TAB_SCROLL_POSITION -> Mem accepts one tab's vertical fraction
  -> Core sends a targeted Tk scroll command


  == Canonical panel update ==

  RENAME_PANEL
      -> UPDATE_PANEL effect with base revision and proposed panel
      -> Mem accepts or conflicts
      -> PANEL_UPDATED or PANEL_UPDATE_CONFLICT reducer event


  == Stage 5 Whiteboards ==

  TEXT_CHANGED updates a Core working snapshot and marks it dirty.
  TEXT_DEBOUNCE may emit UPDATE_PANEL. Mem acceptance clears the dirty state.


  == Stage 6 Whiteboard history ==

  HISTORY_CURSOR_CHANGED changes only the viewed version.
  First TEXT_CHANGED away from HEAD snapshots HEAD, promotes the edited viewed
  text to HEAD, and returns the cursor to HEAD.
