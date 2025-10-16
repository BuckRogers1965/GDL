# State-Driven Game Engine

A declarative, JSON-based game engine for turn-based board games. Define game rules in JSON, not code. No programming required to add new games.

## Philosophy

**Rules emerge from state.** 

Games are state machines where:
1. State determines which actions are legal
2. Actions modify state  
3. Modified state changes legal actions
4. Complex behaviors emerge from simple primitives

## Quick Start

```bash
# Play chess interactively
python3 game.py games/chess.json

# Play checkers with verbose debug output
python3 game.py games/checkers.txt -v

# Run a scripted game
python3 game.py games/checkers.txt saved_games/checker_moves.txt
```

## Features

- ✅ **Zero code for new games** - Add games by writing JSON specifications
- ✅ **Declarative rules** - Conditions and effects, not imperative logic
- ✅ **Multi-step moves** - Chainable actions (checkers jump sequences)
- ✅ **Dynamic promotion** - Conditional state changes (pawn → queen, man → king)
- ✅ **Symmetric rules** - One rule works for all players via player attributes
- ✅ **Path validation** - Line-of-sight checking for sliding pieces
- ✅ **Debug mode** - Verbose output shows rule evaluation step-by-step

Now, there are features that need to be added to support all the features that games will eventually need, these will require code to allow these features to be tested.  And different presentation methods will need to be written and resources added to the game spec as a directory structure. 

## Game Controls

### Input Format
```
A1 B2     # Move from A1 to B2
A1 B2 C3  # Multi-step move (checkers jumps)
quit      # Exit game
```

### Coordinate System
- Columns: A-H (left to right)
- Rows: 1-8 (bottom to top)
- Example: `E2` = column E, row 2

## Included Games

### Chess
Classic chess with standard FIDE rules:
- All standard piece movements
- Pawn promotion to queen
- Captures by moving to occupied square
- **Not yet implemented**: castling, en passant

```bash
python3 game.py chess.json
```

**Sample moves:**
```
E2 E4    # Pawn forward two
G1 F3    # Knight move
F1 C4    # Bishop diagonal
```

### Checkers (American Draughts)
Standard American checkers:
- Men move diagonally forward
- Jump to capture (can chain multiple jumps)
- Kings move/jump in any diagonal direction
- Promotion when reaching opposite end

```bash
python3 game.py checkers.txt
```

**Sample moves:**
```
D3 E4       # Simple move
D3 F5 H7    # Multiple jumps in sequence
```

## Architecture

### Components

**`game.py`** - The game engine
- `GameState` - Holds all game data (board, entities, players, state variables)
- `ExpressionEvaluator` - Interprets condition/effect expressions (game-agnostic)
- `GamePresenter` - Orchestrates game flow and rendering

**Game Specifications** (JSON)
- `chess.json` - Chess rules and setup
- `checkers.txt` - Checkers rules and setup

### How It Works

1. **Load Spec** - Parse JSON game definition
2. **Setup** - Create board, spawn pieces, initialize state
3. **Game Loop**:
   - Render current board state
   - Get player input (start → target positions)
   - **Validate**: Check all action conditions against current state
   - **Execute**: Apply effects if valid, reject if invalid
   - **Update**: Change turn, modify state

The engine has **zero game-specific code**. It only knows how to evaluate expressions against state.

## Game Specification Format

A game spec has 7 sections:

### 1. Metadata
```json
{
  "metadata": {
    "name": "Chess",
    "description": "The classic game of chess",
    "version": "1.0"
  }
}
```

### 2. Players
```json
{
  "players": {
    "roles": [
      { 
        "name": "White", 
        "attributes": { 
          "pawn_direction": 1,
          "promotion_row": 7 
        } 
      }
    ]
  }
}
```

Player attributes enable symmetric rules (same rule works for both players).

### 3. Entity Schemas
```json
{
  "entity_schemas": {
    "types": {
      "Piece": {
        "attributes": {
          "owner": { "type": "player_ref" },
          "rank": { "type": "string", "default": "pawn" }
        }
      }
    }
  }
}
```

### 4. Topology
```json
{
  "topology": {
    "type": "discrete",
    "structure": "grid(8, 8)"
  }
}
```

### 5. State Schema
```json
{
  "state_schema": {
    "global": {
      "current_player": { 
        "type": "player_ref", 
        "initial": "player('White')" 
      }
    }
  }
}
```

Global state variables that can be referenced in conditions and modified by effects.

### 6. Setup
```json
{
  "setup": {
    "steps": [
      {
        "action": "spawn_entity",
        "schema": "Piece",
        "set_attributes": { "owner": "player('White')", "rank": "pawn" },
        "at": ["grid_nodes(0,1, 7,1)"]
      }
    ]
  }
}
```

### 7. Interactions
```json
{
  "interactions": {
    "list": {
      "pawn_move": {
        "conditions": [
          "eq(entity.owner, state.current_player)",
          "eq(entity.rank, 'pawn')",
          "eq(board[target], null)",
          "eq(sub(target.y, start.y), entity.owner.pawn_direction)"
        ],
        "effects": [
          "set(board[start], null)",
          "set(board[target], entity)",
          "set(entity.pos, target)",
          "if(eq(target.y, entity.owner.promotion_row), set(entity.rank, 'queen'))"
        ]
      }
    }
  }
}
```

**Conditions** - Must all evaluate to `true` for action to be valid  
**Effects** - State modifications to apply when action executes  
**Chainable** - Whether action can be part of multi-step sequence

## Expression Language

### Comparison
- `eq(a, b)` - equality
- `ne(a, b)` - inequality
- `gt(a, b)`, `lt(a, b)` - greater/less than

### Logic
- `and(a, b, ...)` - all true
- `or(a, b, ...)` - any true
- `not(a)` - negation

### Math
- `abs(x)` - absolute value
- `sub(a, b)` - subtraction
- `mul(a, b, ...)` - multiplication

### Game Functions
- `mid_pos(start, target)` - calculate midpoint
- `path_clear(start, target)` - check if path is unobstructed
- `other_player(p)` - get opponent

### Property Access
- `entity.owner.pawn_direction` - nested properties
- `board[target]` - array/dict indexing
- `state.current_player` - global state access

## Debug Mode

Use `-v` flag to see detailed rule evaluation:

```bash
python3 game.py chess.json -v
```

Output shows:
- Which action is being tested
- Each condition evaluation result
- Path clear calculations
- Midpoint calculations

Example output:
```
--- DEBUG: Validating segment (3, 1) -> (3, 3) ---
  Testing action: 'pawn_move_one'
    Condition 1: eq(entity.owner, state.current_player) -> Result: True
    Condition 2: eq(entity.rank, 'pawn') -> Result: True
    Condition 3: eq(board[target], null) -> Result: True
    Condition 4: eq(target.x, start.x) -> Result: True
    Condition 5: eq(sub(target.y, start.y), entity.owner.pawn_direction) -> Result: False
  ✗ Action 'pawn_move_one' FAILED.
  Testing action: 'pawn_move_two'
    ...
  ✓ Action 'pawn_move_two' SUCCEEDED.
```

## Scripted Games

Create a text file with one move per line:

**moves.txt**
```
D3 E4
C6 B5
E2 D3
B5 A4
E4 F5
E6 G4 E2
```

Run with:
```bash
python3 game.py checkers.txt moves.txt
```

The game executes moves automatically with 1-second pauses. Switches to interactive mode when script ends or if an invalid move is encountered.

## Creating New Games

1. Copy `chess.json` or `checkers.txt` as a template
2. Modify the 7 sections for your game rules
3. Run: `python3 game.py your_game.json`

No code changes needed!

### Design Tips

**Use player attributes for symmetry:**
```json
"conditions": [
  "eq(sub(target.y, start.y), entity.owner.direction)"
]
```
This one condition works for both players moving in opposite directions.

**Chain actions for multi-step moves:**
```json
"jump": {
  "chainable": true,
  "conditions": [...],
  "effects": [...]
}
```

**Use conditional effects for promotions:**
```json
"effects": [
  "set(board[target], entity)",
  "if(eq(target.y, entity.owner.promotion_row), set(entity.rank, 'queen'))"
]
```

**State variables enable dynamic rules:**
```json
"state_schema": {
  "global": {
    "turn_direction": { "type": "int", "initial": 1 }
  }
}
```
Then reference in conditions: `eq(state.turn_direction, 1)`

## Future Extensions

### Planned Features
- 🎲 **Randomness** - Dice rolling, card shuffling
- 🃏 **Card games** - Decks, hands, hidden information
- 🗺️ **Network topology** - For games like Risk, Catan
- 💰 **Resource management** - Inventory, currency, VP tracking
- ⏱️ **Turn phases** - Multiple phases per turn (draw, play, discard)
- 👁️ **Visibility** - Private information (hands, hidden cards)

### Potential Games
- **Card games**: Uno, Poker, Blackjack, Magic: The Gathering
- **Territory games**: Risk, Diplomacy, Go
- **Economic games**: Monopoly, Catan, Ticket to Ride
- **Abstract games**: Othello, Connect Four, Mancala

## Requirements

- Python 3.7+
- No external dependencies

## Project Structure

```
.
├── game.py          # Game engine (interpreter)
├── chess.json       # Chess game specification
├── checkers.txt     # Checkers game specification
├── moves.txt        # Example scripted moves (optional)
└── README.md        # This file
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Particularly:
- New game specifications
- Expression language functions
- Topology types (networks, zones)
- AI opponents
- Web UI

## Learn More

See the academic paper: [A State-Driven Game Description Language for Turn-Based Games](./paper.md)

---

**Remember**: In this engine, rules are not code. Rules are data. State determines everything.
