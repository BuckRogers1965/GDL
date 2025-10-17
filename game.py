import json
import re
import os
import sys
import copy
import time
import random

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

    def __repr__(self):
        return f"Player({self.name})"

class Zone:
    def __init__(self, name, zone_type, owner=None, visible=True, ordered=True, visible_to=None):
        self.name = name
        self.type = zone_type
        self.owner = owner
        self.visible = visible
        self.ordered = ordered
        self.visible_to = visible_to or []
        self.entities = []

    def __repr__(self):
        return f"Zone({self.name}, {len(self.entities)} entities)"

class Entity:
    _id_counter = 0
    def __init__(self, schema, owner, attributes):
        self.id = Entity._id_counter
        Entity._id_counter += 1
        self.schema = schema
        self.owner = owner
        self.rank = attributes.get('rank', 'man')
        self.pos = None

        for key, value in attributes.items():
            if key not in ['owner', 'rank']:
                setattr(self, key, value)

    def __repr__(self):
        if hasattr(self, 'color') and hasattr(self, 'rank'):
            return f"Entity(id={self.id}, {getattr(self, 'color', '?')}-{self.rank})"
        return f"Entity(id={self.id}, schema={self.schema})"

class GameState:
    def __init__(self):
        self.players = {}
        self.entities = {}
        self.board = {}
        self.zones = {}
        self.current_player = None
        self.topology = {}
        self.current_phase = None

class ExpressionEvaluator:
    def __init__(self, game_state):
        self.state = game_state
        self.verbose = False

    def eval(self, expr, context=None):
        context = context or {}
        expr = expr.strip()

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
                if isinstance(obj, (list, tuple)) and isinstance(key, int):
                    if 0 <= key < len(obj):
                        return obj[key]
                return None

        if '(' in expr:
            # Check if this is part of a property access chain
            dot_pos = expr.find('.')
            if dot_pos > -1 and dot_pos < expr.find('('):
                 # This is a method call on an object, handle with _get_property
                 return self._get_property(expr, context)

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
                    if paren_depth == 0 and expr.endswith(')'): # ensure it's a function call not `a(b).c`
                        args_str = expr[func_start+1:i]
                        args = self._parse_args(args_str, context)
                        return self._call_function(func_name, args, context)

        if '.' in expr and not expr.startswith("'"):
            return self._get_property(expr, context)

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

        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except:
            pass

        return context.get(expr)

    def _parse_args(self, args_str, context):
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
    
    # --- START OF FUCKING FIX ---
    def _get_property(self, path, context):
        # Split only on the first dot to separate the base from the rest of the chain
        parts = path.split('.', 1)
        base_expr = parts[0]
        
        # Recursively evaluate the base expression. This is the key.
        # It allows the base to be a simple variable ('entity') or a function call ('top_card(...)')
        obj = self.eval(base_expr, context)

        if obj is None:
            return None
        
        # If there's more to the chain, process it
        if len(parts) > 1:
            rest_of_path = parts[1]
            for part in rest_of_path.split('.'):
                if obj is None: return None

                if hasattr(obj, part):
                    obj = getattr(obj, part)
                elif isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    return None
        
        return obj
    # --- END OF FUCKING FIX ---

    def _call_function(self, func_name, args, context):
        if self.verbose and not context.get('mute_debug', False):
            log_args = []
            for arg in args:
                if isinstance(arg, (Player, Entity, Zone)):
                    log_args.append(repr(arg))
                elif isinstance(arg, str):
                    log_args.append(f"'{arg}'")
                else:
                    log_args.append(str(arg))
            print(f"      DEBUG[eval]: {func_name}({', '.join(log_args)})")

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
        elif func_name == 'gte':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] >= args[1]
            return False
        elif func_name == 'lte':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] <= args[1]
            return False
        elif func_name == 'and':
            return all(args)
        elif func_name == 'or':
            return any(args)
        elif func_name == 'not':
            return not args[0] if len(args) == 1 else False
        elif func_name == 'abs':
            return abs(args[0]) if len(args) == 1 and args[0] is not None else 0
        elif func_name == 'sub':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] - args[1]
            return 0
        elif func_name == 'add':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] + args[1]
            return 0
        elif func_name == 'mul':
            result = 1
            for a in args:
                if a is not None:
                    result *= a
            return result
        elif func_name == 'mod':
            if len(args) == 2 and args[0] is not None and args[1] is not None:
                return args[0] % args[1]
            return 0
        elif func_name == 'count':
            obj = args[0] if args else None
            if isinstance(obj, Zone):
                return len(obj.entities)
            elif isinstance(obj, list):
                return len(obj)
            return 0
        elif func_name == 'zone':
            zone_name = args[0] if args else None
            return self.state.zones.get(zone_name)
        elif func_name == 'entities_in_zone':
            zone_name = args[0] if args else None
            zone = self.state.zones.get(zone_name)
            return zone.entities if zone else []
        elif func_name == 'random_int':
            min_val = args[0] if len(args) > 0 else 1
            max_val = args[1] if len(args) > 1 else 6
            return random.randint(min_val, max_val)
        elif func_name == 'shuffle':
            zone = args[0] if args else None
            if isinstance(zone, Zone):
                random.shuffle(zone.entities)
            return None
        elif func_name == 'draw_card':
            source_zone = args[0] if args else None
            dest_zone = args[1] if len(args) > 1 else None
            count = args[2] if len(args) > 2 else 1

            if isinstance(source_zone, Zone) and isinstance(dest_zone, Zone):
                drawn = []
                for _ in range(min(count, len(source_zone.entities))):
                    if source_zone.entities:
                        card = source_zone.entities.pop(0)
                        dest_zone.entities.append(card)
                        card.pos = dest_zone
                        drawn.append(card)
                return drawn
            return []
        elif func_name == 'mid_pos':
            start, target = args
            if isinstance(start, dict):
                start = (start['x'], start['y'])
            if isinstance(target, dict):
                target = (target['x'], target['y'])
            mid_point = ((start[0] + target[0]) // 2, (start[1] + target[1]) // 2)
            if self.verbose:
                print(f"      DEBUG[mid_pos]: {start} -> {target} = {mid_point}")
            return mid_point
        elif func_name == 'path_clear':
            start, target = args
            if isinstance(start, dict):
                start = (start['x'], start['y'])
            if isinstance(target, dict):
                target = (target['x'], target['y'])
            dx = 0 if target[0] == start[0] else (1 if target[0] > start[0] else -1)
            dy = 0 if target[1] == start[1] else (1 if target[1] > start[1] else -1)
            current_x, current_y = start[0] + dx, start[1] + dy
            while (current_x, current_y) != target:
                if self.state.board.get((current_x, current_y)) is not None:
                    if self.verbose:
                        print(f"      DEBUG[path_clear]: Blocked at ({current_x}, {current_y})")
                    return False
                current_x += dx
                current_y += dy
            if self.verbose:
                print(f"      DEBUG[path_clear]: Clear from {start} to {target}")
            return True
        elif func_name == 'other_player':
            current = args[0]
            for player in self.state.players.values():
                if player != current:
                    return player
            return None
        elif func_name == 'next_player':
            current = args[0] if args else self.state.current_player
            direction = args[1] if len(args) > 1 else 1
            player_list = list(self.state.players.values())
            if not player_list or current not in player_list:
                return None
            current_idx = player_list.index(current)
            next_idx = (current_idx + direction) % len(player_list)
            return player_list[next_idx]
        elif func_name == 'top_card':
            zone = args[0] if args else None
            if isinstance(zone, Zone) and zone.entities:
                return zone.entities[-1]
            return None
        elif func_name == 'concat':
            return "".join(map(str, args))

        return None

# The rest of the file is unchanged
class GamePresenter:
    def __init__(self, spec_file, presentation_profile='ascii', verbose=False, num_players=None):
        print(f"Loading spec from {spec_file}...")
        with open(spec_file, 'r') as f:
            self.spec = json.load(f)

        self.state = GameState()
        self.evaluator = ExpressionEvaluator(self.state)
        self.profile = presentation_profile
        self.presentation_spec = self.spec.get('presentation', {}).get('profiles', {}).get(self.profile, {})

        self.verbose = verbose
        self.evaluator.verbose = self.verbose
        self.num_players = num_players
        self.current_viewer = None

        print(f"Successfully loaded game: {self.spec['metadata']['name']} with '{self.profile}' profile")

    def _get_player_by_name(self, name):
        return self.state.players.get(name)

    def _parse_location_string(self, loc_str):
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
                    locs.append((x, y))
            return locs
        elif loc_str.startswith("zone("):
            match = re.search(r"zone\('([^']+)'\)", loc_str)
            if match:
                zone_name = match.group(1)
                return [zone_name]
        return []

    def setup_game(self):
        print("--- Setting up game ---")

        player_spec = self.spec['players']
        min_players = player_spec['count'].get('min', 2)
        max_players = player_spec['count'].get('max', 2)

        if self.num_players is None:
            self.num_players = min_players
        elif self.num_players < min_players or self.num_players > max_players:
            print(f"Error: Player count must be between {min_players} and {max_players}")
            sys.exit(1)

        roles = player_spec['roles']
        if player_spec.get('dynamic_roles', False):
            for i in range(self.num_players):
                player_name = f"Player{i+1}"
                attrs = roles[0].get('attributes', {}).copy() if roles else {}
                player = Player(player_name, attrs)
                self.state.players[player.name] = player
        else:
            for i, role in enumerate(roles[:self.num_players]):
                player = Player(role['name'], role.get('attributes', {}))
                self.state.players[player.name] = player

        topo = self.spec['topology']
        if topo['type'] == 'discrete':
            parts = re.findall(r'\d+', topo['structure'])
            self.state.topology = {'type': 'grid', 'width': int(parts[0]), 'height': int(parts[1])}
        elif topo['type'] == 'zones':
            self.state.topology = {'type': 'zones'}
            for zone_name, zone_def in topo['zones'].items():
                owner = None
                if 'owner' in zone_def:
                    owner_match = re.search(r"player\('([^']+)'\)", zone_def['owner'])
                    if owner_match:
                        player_name = owner_match.group(1)
                        owner = self._get_player_by_name(player_name)
                        if not owner: continue

                visible_to = []
                if 'visible_to' in zone_def:
                    if isinstance(zone_def['visible_to'], list):
                        for v in zone_def['visible_to']:
                            player_match = re.search(r"player\('([^']+)'\)", str(v))
                            if player_match:
                                p = self._get_player_by_name(player_match.group(1))
                                if p:
                                    visible_to.append(p)

                zone = Zone(
                    zone_name,
                    zone_def.get('type', 'stack'),
                    owner=owner,
                    visible=zone_def.get('visible', True),
                    ordered=zone_def.get('ordered', True),
                    visible_to=visible_to
                )
                self.state.zones[zone_name] = zone

        for var_name, var_def in self.spec.get('state_schema', {}).get('global', {}).items():
            initial_value = var_def['initial']
            match = None
            if isinstance(initial_value, str):
                match = re.search(r"player\('(\w+)'\)", initial_value)
            if match:
                player_name = match.group(1)
                setattr(self.state, var_name, self._get_player_by_name(player_name))
            else:
                try:
                    setattr(self.state, var_name, int(initial_value))
                except (TypeError, ValueError):
                    setattr(self.state, var_name, initial_value)

        for step in self.spec.get('setup', {}).get('steps', []):
            self._execute_setup_step(step)

        self.state.current_phase = self.spec.get('game_flow', {}).get('initial_phase', 'main_turn')

        print(f"--- Setup complete. {len(self.state.entities)} entities created. ---")

    def _execute_setup_step(self, step):
        action = step['action']

        if action == 'spawn_entity':
            schema = step['schema']
            attrs = step.get('set_attributes', {})

            owner = None
            if 'owner' in attrs:
                owner_match = re.search(r"player\('([^']+)'\)", attrs.get('owner', ''))
                if owner_match:
                    owner = self._get_player_by_name(owner_match.group(1))

            parsed_attrs = {}
            for key, value in attrs.items():
                if key == 'owner':
                    continue
                if isinstance(value, str) and value.startswith("player('"):
                    player_match = re.search(r"player\('([^']+)'\)", value)
                    if player_match:
                        parsed_attrs[key] = self._get_player_by_name(player_match.group(1))
                else:
                    parsed_attrs[key] = value

            locations = []
            for loc in step.get('at', []):
                locations.extend(self._parse_location_string(loc))

            for loc in locations:
                entity = Entity(schema, owner, parsed_attrs)

                if isinstance(loc, tuple):
                    entity.pos = loc
                    self.state.board[loc] = entity
                else:
                    zone = self.state.zones.get(loc)
                    if zone:
                        entity.pos = zone
                        zone.entities.append(entity)

                self.state.entities[entity.id] = entity

        elif action == 'shuffle_zone':
            zone_name = step.get('zone')
            zone = self.state.zones.get(zone_name)
            if zone:
                random.shuffle(zone.entities)

        elif action == 'deal_cards':
            from_zone_name = step.get('from')
            to_zones_exprs = step.get('to', [])
            count = step.get('count', 1)

            from_zone = None
            if from_zone_name:
                zone_match = re.search(r"zone\('([^']+)'\)", from_zone_name)
                if zone_match:
                    from_zone = self.state.zones.get(zone_match.group(1))

            if from_zone:
                active_to_zones = []
                for to_zone_expr in to_zones_exprs:
                    zone_match = re.search(r"zone\('([^']+)'\)", to_zone_expr)
                    if zone_match:
                        to_zone = self.state.zones.get(zone_match.group(1))
                        if to_zone:
                             active_to_zones.append(to_zone)

                if active_to_zones:
                    for _ in range(count):
                        for to_zone in active_to_zones:
                            if from_zone.entities:
                                card = from_zone.entities.pop(0)
                                to_zone.entities.append(card)
                                card.pos = to_zone

        elif action == 'move_card':
            from_zone_name = step.get('from')
            to_zone_name = step.get('to')
            count = step.get('count', 1)

            from_match = re.search(r"zone\('([^']+)'\)", from_zone_name)
            to_match = re.search(r"zone\('([^']+)'\)", to_zone_name)

            if from_match and to_match:
                from_zone = self.state.zones.get(from_match.group(1))
                to_zone = self.state.zones.get(to_match.group(1))

                if from_zone and to_zone:
                    for _ in range(min(count, len(from_zone.entities))):
                        if from_zone.entities:
                            card = from_zone.entities.pop(0)
                            to_zone.entities.append(card)
                            card.pos = to_zone

    def get_asset_for_entity(self, entity, hide=False):
        if hide:
            return self.presentation_spec.get('card_back', '??')

        assets = self.presentation_spec.get('entity_assets', [])
        context = {'entity': entity, 'mute_debug': True}
        for asset_def in assets:
            cond = asset_def['conditions']
            asset_string = asset_def['asset']
            if '#' in asset_string:
                if self.evaluator.eval(cond, context):
                    return asset_string.replace('#', entity.rank)
            else:
                 if self.evaluator.eval(cond, context):
                    return asset_string
        return '?'

    def render_board(self):
        if self.state.topology.get('type') == 'grid':
            self._render_grid_board()
        elif self.state.topology.get('type') == 'zones':
            self._render_zone_board()

    def _render_grid_board(self):
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

    def _render_zone_board(self):
        print("\n" + "="*60)

        for zone_name, zone in self.state.zones.items():
            if not zone.owner:
                self._render_zone(zone, public=True)

        if self.current_viewer:
            for player in self.state.players.values():
                if player != self.current_viewer:
                    for zone_name, zone in self.state.zones.items():
                        if zone.owner == player:
                            self._render_zone(zone, public=False)
            for zone_name, zone in self.state.zones.items():
                 if zone.owner == self.current_viewer:
                    self._render_zone(zone, public=False)

        print("="*60 + "\n")

    def _render_zone(self, zone, public=True):
        if zone.owner:
            if zone.owner == self.current_viewer:
                print(f"\n{zone.owner.name}'s HAND:")
                if not zone.entities:
                    print("  (empty)")
                else:
                    for i, entity in enumerate(zone.entities):
                        asset = self.get_asset_for_entity(entity, hide=False)
                        print(f"  [{i+1}] {asset}")
            else:
                print(f"\n{zone.owner.name}'s HAND:")
                print(f"  {len(zone.entities)} cards (hidden)")

        else:
            print(f"\n{zone.name.upper().replace('_', ' ')}:")
            if not zone.entities:
                print("  (empty)")
            elif not zone.visible:
                print(f"  {len(zone.entities)} cards (hidden)")
            else:
                top_card = zone.entities[-1] if zone.entities else None
                if top_card:
                    asset = self.get_asset_for_entity(top_card, hide=False)
                    print(f"  Top card: {asset} ({len(zone.entities)} total)")
                else:
                     print("  (empty)")


    def parse_position(self, pos_str):
        if len(pos_str) < 2:
            return None, "Invalid position format"

        try:
            col_char, row_str = pos_str[0].upper(), pos_str[1:]
            if not col_char.isalpha() or not row_str.isdigit():
                return None, "Invalid position format"

            x, y = ord(col_char) - ord('A'), int(row_str) - 1
            width, height = self.state.topology['width'], self.state.topology['height']

            if not (0 <= x < width and 0 <= y < height):
                return None, f"Position {pos_str} is out of bounds"

            return (x, y), None

        except Exception as e:
            return None, f"Error parsing position {pos_str}: {e}"

    def _find_valid_action_for_segment(self, entity, start_pos, target_pos, game_state):
        current_phase = game_state.current_phase or 'main_turn'
        phase_spec = self.spec['game_flow']['phases'].get(current_phase, {})
        allowed_actions = phase_spec.get('allowed_actions', [])

        context = {
            'entity': entity,
            'start': {'x': start_pos[0], 'y': start_pos[1]} if isinstance(start_pos, tuple) else start_pos,
            'target': {'x': target_pos[0], 'y': target_pos[1]} if isinstance(target_pos, tuple) else target_pos,
            'board': game_state.board,
            'state': game_state
        }

        if self.verbose:
            print(f"\n--- DEBUG: Validating segment {start_pos} -> {target_pos} ---")

        for action_name in allowed_actions:
            action_spec = self.spec['interactions']['list'].get(action_name, {})
            conditions = action_spec.get('conditions', [])

            if self.verbose:
                print(f"  Testing action: '{action_name}'")

            all_met = True
            for i, condition in enumerate(conditions):
                result = self.evaluator.eval(condition, context)
                if self.verbose:
                    print(f"    Condition {i+1}: {condition} -> {result}")
                if not result:
                    all_met = False
                    break

            if all_met:
                if self.verbose:
                    print(f"  ✓ Action '{action_name}' SUCCEEDED.")
                return action_name, action_spec

        if self.verbose:
            print(f"--- No valid action found ---")
        return None, None

    def _apply_effects_for_segment(self, action_name, entity, start_pos, target_pos, game_state):
        action_spec = self.spec['interactions']['list'].get(action_name, {})
        effects = action_spec.get('effects', [])

        context = {
            'entity': entity,
            'start': start_pos,
            'target': target_pos,
            'board': game_state.board,
            'state': game_state
        }

        for effect in effects:
            self._apply_effect(effect, context)

    def process_move_path(self, original_entity, path):
        sim_state = copy.deepcopy(self.state)
        self.evaluator.state = sim_state

        sim_entity = sim_state.entities[original_entity.id]
        is_multi_segment = len(path) > 2

        if self.verbose:
            print(f"\nDEBUG: Processing path {path}")

        for i in range(len(path) - 1):
            start_pos = path[i]
            target_pos = path[i+1]

            if self.verbose:
                print(f"  Segment {i+1}: {start_pos} -> {target_pos}")

            action_name, action_spec = self._find_valid_action_for_segment(
                sim_entity, start_pos, target_pos, sim_state
            )

            if not action_name:
                self.evaluator.state = self.state
                return False, "Invalid move sequence."

            if is_multi_segment and not action_spec.get('chainable', False):
                self.evaluator.state = self.state
                return False, f"Action '{action_name}' cannot be chained."

            if self.verbose:
                print(f"  ✓ Segment valid with action: {action_name}")

            self._apply_effects_for_segment(action_name, sim_entity, start_pos, target_pos, sim_state)

        self.state = sim_state
        self.evaluator.state = self.state

        if self.verbose:
            print(f"✓ Path successfully executed.")

        turn_change_context = {'state': self.state}
        if len(self.state.players) == 2:
            self.state.current_player = self.evaluator._call_function(
                'other_player', [self.state.current_player], turn_change_context
            )
        else:
            direction = getattr(self.state, 'turn_direction', 1)
            self.state.current_player = self.evaluator._call_function(
                'next_player', [self.state.current_player, direction], turn_change_context
            )

        return True, "Move successful."

    def process_card_action(self, player, card_index, target_data=None):
        hand_zone = None
        for zone in self.state.zones.values():
            if zone.owner == player and 'hand' in zone.name.lower():
                hand_zone = zone
                break

        if not hand_zone:
            return False, "No hand zone found."

        current_phase = self.state.current_phase or 'main_turn'
        phase_spec = self.spec['game_flow']['phases'].get(current_phase, {})
        allowed_actions = phase_spec.get('allowed_actions', [])
        
        actions_to_check = []
        card = None
        
        if card_index == -1: # This corresponds to the user inputting "0"
            actions_to_check = ['draw_card']
        else:
            if card_index < 0 or card_index >= len(hand_zone.entities):
                return False, "Invalid card number."
            card = hand_zone.entities[card_index]
            actions_to_check = allowed_actions


        context = {
            'entity': card,
            'card': card,
            'player': player,
            'state': self.state,
            'target': target_data,
            'hand_zone': hand_zone
        }

        for zone_name, zone_obj in self.state.zones.items():
            context[zone_name] = zone_obj


        for action_name in actions_to_check:
            action_spec = self.spec['interactions']['list'].get(action_name, {})
            if not action_spec: continue

            conditions = action_spec.get('conditions', [])

            if self.verbose:
                print(f"\nTesting action: {action_name}")

            all_met = True
            for condition in conditions:
                # For draw_card, we don't want to check card-specific conditions
                if card is None and 'card.' in condition:
                    continue
                result = self.evaluator.eval(condition, context)
                if self.verbose:
                    print(f"  {condition} -> {result}")
                if not result:
                    all_met = False
                    break

            if all_met:
                effects = action_spec.get('effects', [])
                for effect in effects:
                    self._apply_effect(effect, context)

                if phase_spec.get('auto_advance'):
                    next_phase = phase_spec.get('next_phase')
                    if next_phase:
                        self.state.current_phase = next_phase

                if action_spec.get('end_turn', False):
                    direction = getattr(self.state, 'turn_direction', 1)
                    self.state.current_player = self.evaluator._call_function(
                        'next_player', [self.state.current_player, direction], context
                    )

                if card_index == -1:
                    return True, "Drew a card."
                return True, f"Played {self.get_asset_for_entity(card)}"

        if card_index == -1:
            return False, "Cannot draw a card right now."
        return False, "Cannot play that card."

    def _apply_effect(self, effect_expr, context):
        effect_expr = effect_expr.strip()

        set_match = re.match(r'set\((.+),\s*(.+)\)$', effect_expr)
        if set_match:
            self._set_value(
                set_match.group(1).strip(),
                self.evaluator.eval(set_match.group(2).strip(), context),
                context
            )
            return

        if_match = re.match(r'if\((.+),\s*(.+)\)$', effect_expr)
        if if_match:
            condition = if_match.group(1).strip()
            true_effect = if_match.group(2).strip()
            if self.evaluator.eval(condition, context):
                self._apply_effect(true_effect, context)
            return

        remove_match = re.match(r'remove_entity\((.+)\)$', effect_expr)
        if remove_match:
            entity_to_remove = self.evaluator.eval(remove_match.group(1).strip(), context)
            if entity_to_remove and hasattr(entity_to_remove, 'id'):
                if entity_to_remove.id in context['state'].entities:
                    del context['state'].entities[entity_to_remove.id]
                if hasattr(context['state'], 'board'):
                    for pos, ent in list(context['state'].board.items()):
                        if ent and ent.id == entity_to_remove.id:
                            del context['state'].board[pos]
            return

        move_match = re.match(r'move_to_zone\((.+),\s*(.+)\)$', effect_expr)
        if move_match:
            entity = self.evaluator.eval(move_match.group(1).strip(), context)
            target_zone = self.evaluator.eval(move_match.group(2).strip(), context)

            if entity and isinstance(target_zone, Zone):
                if isinstance(entity.pos, Zone):
                    if entity in entity.pos.entities:
                        entity.pos.entities.remove(entity)

                target_zone.entities.append(entity)
                entity.pos = target_zone
            return

        draw_match = re.match(r'draw_cards\((.+),\s*(.+),\s*(.+)\)$', effect_expr)
        if draw_match:
            source = self.evaluator.eval(draw_match.group(1).strip(), context)
            dest = self.evaluator.eval(draw_match.group(2).strip(), context)
            count = self.evaluator.eval(draw_match.group(3).strip(), context)

            if isinstance(source, Zone) and isinstance(dest, Zone):
                for _ in range(min(count, len(source.entities))):
                    if source.entities:
                        card = source.entities.pop(0)
                        dest.entities.append(card)
                        card.pos = dest
            return

    def _set_value(self, target_expr, value, context):
        board_match = re.match(r'board\[(.+)\]$', target_expr)
        if board_match:
            pos = self.evaluator.eval(board_match.group(1).strip(), context)
            if isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                pos = (pos['x'], pos['y'])
            if value is None:
                context['board'].pop(pos, None)
            else:
                context['board'][pos] = value
            return

        if '.' in target_expr:
            parts = target_expr.split('.')
            obj = context.get(parts[0])
            for part in parts[1:-1]:
                if obj is None:
                    return
                obj = getattr(obj, part, None)
            if obj is not None:
                setattr(obj, parts[-1], value)
            return

        if target_expr.startswith('state.'):
            var_name = target_expr[6:]
            setattr(context['state'], var_name, value)
            return

    def run_grid_game(self, moves_file=None):
        moves_to_execute = []
        is_scripted = False

        if moves_file:
            is_scripted = True
            try:
                with open(moves_file, 'r') as f:
                    moves_to_execute = [line.strip() for line in f if line.strip()]
                print(f"--- Running in scripted mode from '{moves_file}' ---")
            except FileNotFoundError:
                print(f"!! Error: Moves file not found at '{moves_file}'")
                return

        while True:
            self.render_board()
            current_player = self.state.current_player
            if not current_player:
                print("Game over or error: No current player.")
                break

            print(f"Turn: {current_player.name}")

            move_input = ""
            if is_scripted and moves_to_execute:
                move_input = moves_to_execute.pop(0)
                print(f"Executing from file: {move_input}")
                time.sleep(0.5)
            else:
                if is_scripted:
                    print("--- End of script. Now in interactive mode. ---")
                    is_scripted = False
                move_input = input(f"Player '{current_player.name}', enter move (e.g., A1 B2) or 'quit': ").strip()

            if move_input.upper() == 'QUIT':
                print("Game ended by user.")
                break

            position_strs = move_input.upper().split()
            if len(position_strs) < 2:
                print("!! A move requires at least a start and end position.")
                continue

            path = []
            valid_path = True
            for pos_str in position_strs:
                pos, error = self.parse_position(pos_str)
                if error:
                    print(f"!! {error}")
                    valid_path = False
                    break
                path.append(pos)

            if not valid_path:
                continue

            entity = self.state.board.get(path[0])
            if not entity:
                print("!! No piece at starting position.")
                continue

            success, message = self.process_move_path(entity, path)
            if not success:
                print(f"!! {message}")
                if is_scripted:
                    print("!! Aborting script. Switching to interactive mode.")
                    is_scripted = False
                continue

    def run_card_game(self):
        while True:
            current_player = self.state.current_player
            if not current_player:
                print("Game over or error: No current player.")
                break

            self.current_viewer = current_player
            self.render_board()

            print(f"\n>>> {current_player.name}'s Turn <<<")

            hand_zone = None
            for zone in self.state.zones.values():
                if zone.owner == current_player and 'hand' in zone.name.lower():
                    hand_zone = zone
                    break

            if not hand_zone or not hand_zone.entities:
                print("You have no cards! Skipping turn.")
                input("Press Enter to continue...")
                direction = getattr(self.state, 'turn_direction', 1)
                self.state.current_player = self.evaluator._call_function(
                    'next_player', [self.state.current_player, direction], {}
                )
                continue

            action_input = input("Enter card # to play, 0 to draw (or 'quit'): ").strip()

            if action_input.upper() == 'QUIT':
                print("Game ended by user.")
                break
            
            try:
                card_num = int(action_input)
                card_index = card_num - 1 # Input '1' -> index 0; Input '0' -> index -1

                success, message = self.process_card_action(current_player, card_index)
                print(f"\n{message}")

                if not success:
                    print("Try again.")
                    time.sleep(1)
                    continue
                else:
                    if hand_zone and not hand_zone.entities:
                        self.render_board()
                        print(f"\n\n*** {current_player.name} WINS! ***")
                        return

            except ValueError:
                print("!! Invalid input. Enter a card number.")
                continue

            input("\nPress Enter to continue...")

    def run(self, moves_file=None):
        self.setup_game()

        if self.state.topology.get('type') == 'grid':
            self.run_grid_game(moves_file)
        elif self.state.topology.get('type') == 'zones':
            self.run_card_game()
        else:
            print("Unknown topology type!")

if __name__ == "__main__":
    verbose_mode = '-v' in sys.argv
    if verbose_mode:
        sys.argv.remove('-v')

    if len(sys.argv) < 2:
        print("Usage: python game.py [-v] <spec_file> [moves_file] [-p num_players]")
        sys.exit(1)

    spec_file = sys.argv[1]
    if not os.path.exists(spec_file):
        print(f"Error: Spec file not found at '{spec_file}'")
        sys.exit(1)

    moves_file = None
    num_players = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '-p' and i + 1 < len(sys.argv):
            try:
                num_players = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid number of players '{sys.argv[i+1]}'")
                sys.exit(1)
        else:
            if moves_file is None and not sys.argv[i].startswith('-'):
                 moves_file = sys.argv[i]
                 i += 1
            else:
                try:
                    num_players = int(sys.argv[i])
                    i += 1
                except ValueError:
                    print(f"Unknown argument or invalid player count: {sys.argv[i]}")
                    sys.exit(1)


    game = GamePresenter(spec_file, verbose=verbose_mode, num_players=num_players)
    game.run(moves_file=moves_file)