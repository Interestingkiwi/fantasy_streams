"""
Contains the core optimization logic for finding the best fantasy lineup
for fantasystreams.

Author: Jason Druckenmiller
Date: 10/20/2025
Updated: 10/20/2025
"""
from functools import lru_cache

def find_optimal_lineup(active_players, lineup_slots, category_weights={}):
    """
    Determines the optimal fantasy lineup from a list of active players for a given day.
    This function uses a recursive approach with memoization (dynamic programming).

    Args:
        active_players (list): A list of player dictionaries.
        lineup_slots (dict): A dictionary of available roster spots, e.g., {'C': 2, 'LW': 2, ...}.
        category_weights (dict): A dictionary mapping stat categories to their weights.

    Returns:
        tuple: A tuple containing two lists:
               - The optimal roster (list of (player_dict, position_str) tuples).
               - The benched players (list of player_dict).
    """
    # Sort players by their marginal value to consider the best players first.
    # This is a heuristic that helps the algorithm find good solutions faster.
    sorted_players = sorted(active_players, key=lambda p: p.get('marginal_value', 0), reverse=True)

    # Separate goalies and skaters as they have different slotting logic.
    eligible_skaters = [p for p in sorted_players if 'G' not in p.get('positions', '').split(', ')]
    eligible_goalies = [p for p in sorted_players if 'G' in p.get('positions', '').split(', ')]

    # Get slot counts for skaters and goalies from the settings
    skater_slots = {pos: count for pos, count in lineup_slots.items() if pos != 'G'}
    goalie_slots_count = lineup_slots.get('G', 0)

    # Order of slots for the recursive solver's state
    ordered_skater_slots = sorted(skater_slots.keys())

    memo = {}

    def solve_skaters(player_index, slots_tuple):
        """Recursive solver for skaters."""
        state = (player_index, slots_tuple)
        if player_index == len(eligible_skaters):
            return 0, []
        if state in memo:
            return memo[state]

        # Convert tuple back to dict for easier processing
        slots = dict(zip(ordered_skater_slots, slots_tuple))
        player = eligible_skaters[player_index]

        # Path 1: Skip (bench) the current player
        best_score, best_lineup = solve_skaters(player_index + 1, slots_tuple)

        # Path 2: Try to place the current player in each of their eligible slots
        player_positions = [p for p in player.get('positions', '').split(', ') if p in slots]
        for pos in player_positions:
            if slots[pos] > 0:
                new_slots = slots.copy()
                new_slots[pos] -= 1

                new_slots_tuple = tuple(new_slots[s] for s in ordered_skater_slots)

                path_score, path_lineup = solve_skaters(player_index + 1, new_slots_tuple)
                current_score = player.get('marginal_value', 0) + path_score

                if current_score > best_score:
                    best_score, best_lineup = current_score, [(player, pos)] + path_lineup

        memo[state] = (best_score, best_lineup)
        return best_score, best_lineup

    # Solve for skaters
    initial_slots_tuple = tuple(skater_slots.get(s, 0) for s in ordered_skater_slots)
    _, optimal_skaters = solve_skaters(0, initial_slots_tuple)

    # Solve for goalies (simpler: just take the best ones up to the slot limit)
    optimal_goalies = [(g, 'G') for g in eligible_goalies[:goalie_slots_count]]

    # Combine results and determine the final bench
    optimal_roster = optimal_skaters + optimal_goalies

    # Identify benched players
    optimal_player_ids = {p['player_id'] for p, _ in optimal_roster}
    benched_players = [p for p in active_players if p['player_id'] not in optimal_player_ids]

    return optimal_roster, benched_players
