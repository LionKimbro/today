# `core.py`

OWNS:
  bounded current world / current application state
  Reducer Core
  Core machine runtime
  Core effects processing
  declarative Tk commands
  Core lifecycle

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
          stack entry + relevant registers
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






