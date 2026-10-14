"""Explicit YA launch profiles and independent transcript qualification."""
DEFAULT_MODELS = {'codex':'gpt-6.1-sol', 'claude':'claude-opus-5-5'}


def launch_request(provider, model, effort, prompt):
    value = {'provider':provider, 'model':model, 'thinking':effort,
             'mode':'bypassPermissions', 'message':prompt,
             'recapMode':'off', 'promptSuggestionMode':'off'}
    if provider == 'codex':
        value['serviceTier'] = 'default'
    return value


def qualify(provider, model, effort, metrics, process):
    contexts = metrics.get('modelContexts', [])
    reasons = []
    if not contexts or any(c.get('model') != model for c in contexts):
        reasons.append('effective_model_missing_or_mismatched')
    if not contexts or any(c.get('effort', c.get('reasoning_effort')) != effort for c in contexts):
        reasons.append('effective_effort_missing_or_mismatched')
    if provider == 'claude':
        if not contexts or any(c.get('speed') != 'standard' or c.get('service_tier') != 'standard' for c in contexts):
            reasons.append('standard_speed_not_reported')
    elif process.get('serviceTier') != 'default':
        reasons.append('codex_standard_thread_tier_not_confirmed')
    return {'qualified':not reasons,'reasons':reasons,
            'speedEvidence':'provider_usage' if provider=='claude' else 'YA_live_thread_tier_and_cleared_guest_config',
            'limits':['Codex rollouts omit service tier; YA thread selection is evidence, not upstream billing attestation.'] if provider=='codex' else []}
