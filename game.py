import json
import re
import os
import sys
import copy
import time

class Player:
    def __init__(self, name, attributes): 
        self.name = name
        self.attributes = attributes
        for key, value in attributes.items():
            setattr(self, key, value)
    
    def __eq__(self, other):
        if not isinstance(other, Player):
            return NotImplemented
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

class Entity:
    _id_counter = 0
    def __init__(self, schema, owner, attributes):
        self.id = Entity._id_counter
        Entity._id_counter += 1
        self.schema = schema
        self.owner = owner
        self.rank = attributes.get('rank', 'man')
        self.pos = None

class GameState:
    def __init__(self):
        self.players = {}
        self.entities = {}
        self.board = {}
        self.current_player = None
        self.topology = {}

class ExpressionEvaluator:
    """Generic expression evaluator - knows NOTHING about game rules"""
    
    def __init__(self, game_state):
        self.state = game_state
        self.verbose = False # Will be set by GamePresenter
        
    def eval(self, expr, context=None):
        """Evaluate an expression string in the given context"""
        context = context or {}
        expr = expr.strip()
        
        # FIX: Bracket access MUST be parsed before function calls.
        if '[' in expr and ']' in expr and not expr.startswith("'"):
            bracket_start = expr.find('[')
            pre_bracket = expr[:bracket_start]
            if '(' not in pre_bracket:
                bracket_end = expr.rfind(']')
                obj_name = expr[:bracket_start].strip()
                key_expr = expr[bracket_start+1:bracket_end].strip()
                
                obj = self.eval(obj_name, context)
                if obj is None:
                    return None
                
                key = self.eval(key_expr, context)
                
                if isinstance(key, dict) and 'x' in key and 'y' in key:
                    key = (key['x'], key['y'])
                
                if isinstance(obj, dict):
                    return obj.get(key)
                return None

        # Parse function call by finding matching parentheses
        if '(' in expr:
            paren_depth = 0
            func_start = -1
            for i, char in enumerate(expr):
                if char == '(':
                    if paren_depth == 0:
                        func_name = expr[:i].strip()
                        func_start = i
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        args_str = expr[func_start+1:i]
                        args = self._parse_args(args_str, context)
                        return self._call_function(func_name, args, context)
        
        # Parse property access: obj.prop or obj.prop.subprop
        if '.' in expr and not expr.startswith("'"):
            return self._get_property(expr, context)
        
        # Parse literal values
        if expr == 'null':
            return None
        if expr == 'true':
            return True
        if expr == 'false':
            return False
        if expr.startswith("'") and expr.endswith("'"):
            return expr[1:-1]
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]
        
        # Try to parse as number
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except:
            pass
            
        # Variable reference
        return context.get(expr)
    
    def _parse_args(self, args_str, context):
        """Parse comma-separated arguments, respecting nested parentheses and brackets"""
        if not args_str.strip():
            return []
        
        args = []
        depth = 0
        current_arg = ""
        
        for char in args_str:
            if char in '([':
                depth += 1
                current_arg += char
            elif char in ')]':
                depth -= 1
                current_arg += char
            elif char == ',' and depth == 0:
                args.append(self.eval(current_arg.strip(), context))
                current_arg = ""
            else:
                current_arg += char
        
        if current_arg.strip():
            args.append(self.eval(current_arg.strip(), context))
        
        return args
    
    def _get_property(self, path, context):
        """Get nested property: entity.owner.direction"""
        parts = path.split('.')
        obj = context.get(parts[0])
        
        if obj is None:
            return None
            
        for part in parts[1:]:
            if obj is None:
                return None
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj
    
    def _call_function(self, func_name, args, context):
        """Call a built-in function"""
        
        # Comparison functions
        if func_name == 'eq':
            return args[0] == args[1] if len(args) == 2 else False
        elif func_name == 'ne':
            return args[0] != args[1] if len(args) == 2 else False
        elif func_name == 'gt':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] > args[1]
            return False
        elif func_name == 'lt':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] < args[1]
            return False
        
        # Logical functions
        elif func_name == 'and':
            return all(args)
        elif func_name == 'or':
            return any(args)
        elif func_name == 'not':
            return not args[0] if len(args) == 1 else False
        
        # Math functions
        elif func_name == 'abs':
            return abs(args[0]) if len(args) == 1 and args[0] is not None else 0
        elif func_name == 'sub':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] - args[1]
            return 0
        elif func_name == 'mul':
            result = 1
            for a in args:
                if a is not None:
                    result *= a
            return result
        
        # Game-specific helper functions
        elif func_name == 'mid_pos':
            start, target = args
            if isinstance(start, dict):
                start = (start['x'], start['y'])
            if isinstance(target, dict):
                target = (target['x'], target['y'])
            
            mid_point = ((start[0] + target[0]) // 2, (start[1] + target[1]) // 2)
            if self.verbose:
                print(f"      DEBUG[mid_pos]: Calculating midpoint between {start} and {target}. Result: {mid_point}")
            return mid_point

        elif func_name == 'path_clear':
            start, target = args
            if isinstance(start, dict):
                start = (start['x'], start['y'])
            if isinstance(target, dict):
                target = (target['x'], target['y'])
            
            # Calculate direction of movement
            dx = 0 if target[0] == start[0] else (1 if target[0] > start[0] else -1)
            dy = 0 if target[1] == start[1] else (1 if target[1] > start[1] else -1)
            
            # Check all squares between start and target (exclusive)
            current_x, current_y = start[0] + dx, start[1] + dy
            while (current_x, current_y) != target:
                if self.state.board.get((current_x, current_y)) is not None:
                    if self.verbose:
                        print(f"      DEBUG[path_clear]: Path blocked at ({current_x}, {current_y})")
                    return False
                current_x += dx
                current_y += dy

            if self.verbose:
                print(f"      DEBUG[path_clear]: Path clear from {start} to {target}")
            return True
        
        elif func_name == 'other_player':
            current = args[0]
            for player in self.state.players.values():
                if player != current:
                    return player
            return None
        
        return None

class GamePresenter:
    def __init__(self, spec_file, presentation_profile='ascii', verbose=False):
        print(f"Loading spec from {spec_file}...")
        with open(spec_file, 'r') as f:
            self.spec = json.load(f)
        self.state = GameState()
        self.evaluator = ExpressionEvaluator(self.state)
        self.profile = presentation_profile
        self.presentation_spec = self.spec.get('presentation', {}).get('profiles', {}).get(self.profile, {})
        if not self.presentation_spec: 
            print(f"Warning: Presentation profile '{self.profile}' not found.")
        
        self.verbose = verbose
        self.evaluator.verbose = self.verbose # Sync verbose flag to evaluator

        print(f"Successfully loaded game: {self.spec['metadata']['name']} with '{self.profile}' profile")

    def _get_player_by_name(self, name):
        return self.state.players.get(name)

    def _parse_location_string(self, loc_str):
        """Parse location expressions from setup"""
        if "grid_nodes" in loc_str:
            match = re.search(r'grid_nodes\((.*?)\)', loc_str)
            if not match: 
                return []
            coord_string = match.group(1)
            parts = [int(p) for p in re.findall(r'\d+', coord_string)]
            if len(parts) != 4: 
                return []
            x_min, y_min, x_max, y_max = parts
            locs = []
            for y in range(y_min, y_max + 1):
                for x in range(x_min, x_max + 1):
                    # REMOVE THE CHECKERS FILTER: if (x + y) % 2 != 0:
                    locs.append((x, y))
            return locs
        return []

    def _parse_location_string_old(self, loc_str):
        """Parse location expressions from setup"""
        if "grid_nodes" in loc_str:
            match = re.search(r'grid_nodes\((.*?)\)', loc_str)
            if not match: 
                return []
            coord_string = match.group(1)
            parts = [int(p) for p in re.findall(r'\d+', coord_string)]
            if len(parts) != 4: 
                return []
            x_min, y_min, x_max, y_max = parts
            locs = []
            for y in range(y_min, y_max + 1):
                for x in range(x_min, x_max + 1):
                    if (x + y) % 2 != 0: 
                        locs.append((x, y))
            return locs
        return []

    def setup_game(self):
        print("--- Setting up game ---")
    
        # Create players
        for role in self.spec['players']['roles']:
            player = Player(role['name'], role.get('attributes', {}))
            self.state.players[player.name] = player
    
        # Set up topology
        parts = re.findall(r'\d+', self.spec['topology']['structure'])
        self.state.topology = {'type': 'grid', 'width': int(parts[0]), 'height': int(parts[1])}
    
        # Initialize global state variables (like current_player)
        for var_name, var_def in self.spec['state_schema']['global'].items():
            initial_value = var_def['initial']
            # Extract player name from "player('Name')" pattern
            match = re.search(r"player\('(\w+)'\)", initial_value)
            if match:
                player_name = match.group(1)
                setattr(self.state, var_name, self._get_player_by_name(player_name))
    
        # Spawn entities according to setup steps
        for step in self.spec['setup']['steps']:
            if step['action'] == 'spawn_entity':
                schema = step['schema']
                attrs = step['set_attributes']
            
                # Extract owner name from "player('Name')" pattern
                owner_expr = attrs.get('owner', '')
                owner_match = re.search(r"player\('(\w+)'\)", owner_expr)
                if owner_match:
                    owner_name = owner_match.group(1)
                    owner = self._get_player_by_name(owner_name)
                else:
                    owner = None
            
                # Get all locations for this spawn step
                locations = []
                for loc in step['at']: 
                    locations.extend(self._parse_location_string(loc))
            
                # Create entities at each location
                for pos in locations:
                    entity = Entity(schema, owner, attrs)
                    entity.pos = pos
                    self.state.entities[entity.id] = entity
                    self.state.board[pos] = entity
    
        print(f"--- Setup complete. {len(self.state.entities)} entities on board. ---")

    def setup_game_old(self):
        print("--- Setting up game ---")
        
        for role in self.spec['players']['roles']:
            player = Player(role['name'], role.get('attributes', {}))
            self.state.players[player.name] = player
        
        parts = re.findall(r'\d+', self.spec['topology']['structure'])
        self.state.topology = {'type': 'grid', 'width': int(parts[0]), 'height': int(parts[1])}
        
        for var_name, var_def in self.spec['state_schema']['global'].items():
            if "player('Red')" in var_def['initial']:
                setattr(self.state, var_name, self._get_player_by_name('Red'))
        
        for step in self.spec['setup']['steps']:
            if step['action'] == 'spawn_entity':
                schema = step['schema']
                attrs = step['set_attributes']
                owner_name = attrs['owner'].replace("player('", "").replace("')", "")
                owner = self._get_player_by_name(owner_name)
                
                locations = []
                for loc in step['at']: 
                    locations.extend(self._parse_location_string(loc))
                
                for pos in locations:
                    entity = Entity(schema, owner, attrs)
                    entity.pos = pos
                    self.state.entities[entity.id] = entity
                    self.state.board[pos] = entity
        
        print(f"--- Setup complete. {len(self.state.entities)} entities on board. ---")

    def get_asset_for_entity(self, entity):
        """Get display character for entity"""
        assets = self.presentation_spec.get('entity_assets', [])
        context = {'entity': entity}
        for asset_def in assets:
            cond = asset_def['conditions']
            if self.evaluator.eval(cond, context):
                return asset_def['asset']
        return '?'


    def get_asset_for_entity_old(self, entity):
        """Get display character for entity"""
        assets = self.presentation_spec.get('entity_assets', [])
        for asset_def in assets:
            cond = asset_def['conditions']
            if (f"eq(entity.owner.name, '{entity.owner.name}')" in cond and 
                f"eq(entity.schema, '{entity.schema}')" in cond and
                f"eq(entity.rank, '{entity.rank}')" in cond):
                return asset_def['asset']
        return '?'

    def render_board(self):
        """Display the current board state"""
        width = self.state.topology['width']
        height = self.state.topology['height']
        topo_assets = self.presentation_spec.get('topology_assets', {})
        light_sq = topo_assets.get('empty_light_square', '  ')
        dark_sq = topo_assets.get('empty_dark_square', '##')
        
        print("\n  " + "".join([f" {chr(ord('A') + i)} " for i in range(width)]))
        for y in reversed(range(height)):
            row_str = f"{y+1} "
            for x in range(width):
                entity = self.state.board.get((x, y))
                if entity: 
                    row_str += f" {self.get_asset_for_entity(entity)} "
                else: 
                    row_str += (light_sq if (x+y) % 2 == 0 else dark_sq) + " "
            print(row_str + f" {y+1}")
        print("  " + "".join([f" {chr(ord('A') + i)} " for i in range(width)]))
        print()

    def parse_position(self, pos_str):
        """Parse user input like 'D3' to (x, y) tuple"""
        if len(pos_str) < 2: return None, "Invalid position format"
        
        try:
            col_char, row_str = pos_str[0].upper(), pos_str[1:]
            if not col_char.isalpha() or not row_str.isdigit(): return None, "Invalid position format"
            
            x, y = ord(col_char) - ord('A'), int(row_str) - 1
            width, height = self.state.topology['width'], self.state.topology['height']
            
            if not (0 <= x < width and 0 <= y < height): return None, f"Position {pos_str} is out of bounds"
            
            return (x, y), None
            
        except Exception as e:
            return None, f"Error parsing position {pos_str}: {e}"

    def _find_valid_action_for_segment(self, entity, start_pos, target_pos, game_state):
        """Internal helper to find a valid action for one step, using a given state."""
        current_phase = self.spec['game_flow']['initial_phase']
        allowed_actions = self.spec['game_flow']['phases'][current_phase]['allowed_actions']
        
        context = {
            'entity': entity,
            'start': {'x': start_pos[0], 'y': start_pos[1]},
            'target': {'x': target_pos[0], 'y': target_pos[1]},
            'board': game_state.board,
            'state': game_state
        }
        
        if self.verbose: print(f"\n--- DEBUG: Validating segment {start_pos} -> {target_pos} ---")
        
        for action_name in allowed_actions:
            action_spec = self.spec['interactions']['list'].get(action_name, {})
            conditions = action_spec.get('conditions', [])
            
            if self.verbose: print(f"  Testing action: '{action_name}'")
            
            all_met = True
            for i, condition in enumerate(conditions):
                result = self.evaluator.eval(condition, context)
                if self.verbose: print(f"    Condition {i+1}: {condition} -> Result: {result}")
                if not result:
                    all_met = False
                    break
            
            if all_met:
                if self.verbose:
                    print(f"  ✓ Action '{action_name}' SUCCEEDED.")
                    print(f"--- END DEBUG ---")
                return action_name, action_spec
            elif self.verbose:
                print(f"  ✗ Action '{action_name}' FAILED.")
        
        if self.verbose:
            print(f"--- DEBUG: No valid action found for segment. ---")
            print(f"--- END DEBUG ---")
        return None, None

    def _apply_effects_for_segment(self, action_name, entity, start_pos, target_pos, game_state):
        action_spec = self.spec['interactions']['list'].get(action_name, {})
        effects = action_spec.get('effects', [])
        
        context = {
            'entity': entity, 'start': start_pos, 'target': target_pos,
            'board': game_state.board, 'state': game_state
        }
        
        for effect in effects:
            self._apply_effect(effect, context)
            
    def process_move_path(self, original_entity, path):
        sim_state = copy.deepcopy(self.state)
        self.evaluator.state = sim_state
        
        sim_entity = sim_state.entities[original_entity.id]
        is_multi_segment = len(path) > 2

        if self.verbose: print(f"\nDEBUG: Processing path {path}")
        
        for i in range(len(path) - 1):
            start_pos = path[i]
            target_pos = path[i+1]
            
            if self.verbose: print(f"  Segment {i+1}: {start_pos} -> {target_pos}")
            
            action_name, action_spec = self._find_valid_action_for_segment(sim_entity, start_pos, target_pos, sim_state)
            
            if not action_name:
                self.evaluator.state = self.state; return False, "Invalid move sequence."
            
            if is_multi_segment and not action_spec.get('chainable', False):
                self.evaluator.state = self.state; return False, f"Action '{action_name}' cannot be used in a multi-step move."

            if self.verbose: print(f"  ✓ Segment valid with action: {action_name}")
            
            self._apply_effects_for_segment(action_name, sim_entity, start_pos, target_pos, sim_state)

        self.state = sim_state
        self.evaluator.state = self.state
        if self.verbose: print(f"✓ Path successfully executed.")

        turn_change_context = {'state': self.state}
        self.state.current_player = self.evaluator._call_function('other_player', [self.state.current_player], turn_change_context)
        return True, "Move successful."

    def _apply_effect(self, effect_expr, context):
        effect_expr = effect_expr.strip()
        
        set_match = re.match(r'set\((.+),\s*(.+)\)$', effect_expr)
        if set_match:
            self._set_value(set_match.group(1).strip(), self.evaluator.eval(set_match.group(2).strip(), context), context); return
        
        if_match = re.match(r'if\((.+),\s*(.+)\)$', effect_expr)
        if if_match:
            if self.evaluator.eval(if_match.group(1).strip(), context): self._apply_effect(if_match.group(2).strip(), context)
            return
        
        remove_match = re.match(r'remove_entity\((.+)\)$', effect_expr)
        if remove_match:
            entity_to_remove = self.evaluator.eval(remove_match.group(1).strip(), context)
            if entity_to_remove and hasattr(entity_to_remove, 'id') and entity_to_remove.id in context['state'].entities:
                del context['state'].entities[entity_to_remove.id]
            return

    def _set_value(self, target_expr, value, context):
        board_match = re.match(r'board\[(.+)\]$', target_expr)
        if board_match:
            pos = self.evaluator.eval(board_match.group(1).strip(), context)
            if isinstance(pos, dict) and 'x' in pos and 'y' in pos: pos = (pos['x'], pos['y'])
            if value is None: context['board'].pop(pos, None)
            else: context['board'][pos] = value
            return
        
        if '.' in target_expr:
            parts = target_expr.split('.')
            obj = context.get(parts[0])
            for part in parts[1:-1]:
                if obj is None: return
                obj = getattr(obj, part, None)
            if obj is not None: setattr(obj, parts[-1], value)
            return

    def run(self, moves_file=None):
        self.setup_game()
        moves_to_execute, is_scripted = [], False
        if moves_file:
            is_scripted = True
            try:
                with open(moves_file, 'r') as f:
                    moves_to_execute = [line.strip() for line in f if line.strip()]
                print(f"--- Running in scripted mode from '{moves_file}' ---")
            except FileNotFoundError:
                print(f"!! Error: Moves file not found at '{moves_file}'"); return

        while True:
            self.render_board()
            current_player = self.state.current_player
            if not current_player: print("Game over or error: No current player."); break
            print(f"Turn: {current_player.name}")
            
            move_input = ""
            if is_scripted and moves_to_execute:
                move_input = moves_to_execute.pop(0)
                print(f"Executing from file: {move_input}"); time.sleep(1)
            else:
                if is_scripted: print("--- End of script. Now in interactive mode. ---"); is_scripted = False
                move_input = input(f"Player '{current_player.name}', enter move (format: A1 B2 C3...) or 'quit': ").strip()

            if move_input.upper() == 'QUIT': print("Game ended by user."); break
            position_strs = move_input.upper().split()
            if len(position_strs) < 2: print("!! A move requires at least a start and end position."); continue

            path, valid_path = [], True
            for pos_str in position_strs:
                pos, error = self.parse_position(pos_str)
                if error: print(f"!! {error}"); valid_path = False; break
                path.append(pos)
            if not valid_path: continue

            entity = self.state.board.get(path[0])
            if not entity: print("!! No piece at starting position."); continue

            success, message = self.process_move_path(entity, path)
            if not success:
                print(f"!! {message}")
                if is_scripted: print("!! Aborting script due to invalid move. Switching to interactive mode."); is_scripted = False
                continue

if __name__ == "__main__":
    verbose_mode = '-v' in sys.argv
    if verbose_mode:
        sys.argv.remove('-v')

    if len(sys.argv) < 2:
        print("Usage: python game.py [-v] <path_to_spec_file> [path_to_moves_file]")
        sys.exit(1)
    
    spec_file = sys.argv[1]
    if not os.path.exists(spec_file):
        print(f"Error: Spec file not found at '{spec_file}'")
        sys.exit(1)
    
    moves_file = None
    if len(sys.argv) > 2:
        moves_file = sys.argv[2]

    game = GamePresenter(spec_file, verbose=verbose_mode)
    game.run(moves_file=moves_file)
