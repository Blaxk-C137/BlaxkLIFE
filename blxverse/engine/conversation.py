"""Private, bounded cross-channel recall and authoritative casual meeting plans."""
from __future__ import annotations

import re

from blxverse.engine.models import new_id

LIMIT = 80
STOP = set('the a an i you me my your is was are and to for it we that this do did of at in on remember told said'.split())


def tokens(text):
    return set(re.findall(r"[a-z0-9']+", text.lower())) - STOP


def hydrate(sim, npc):
    if npc.flags.get('conversation_version') == 2:
        return
    history = npc.flags.setdefault('conversation_history', [])
    thread = sim.threads.get(npc.id)
    known = {t.get('id') for t in history}
    if thread:
        for msg in thread.messages:
            if msg.id not in known:
                history.append({'id': msg.id, 'user': msg.text if msg.sender == 'player' else '',
                                'reply': msg.text if msg.sender != 'player' else '',
                                'medium': 'text', 'minute': msg.minute})
    history.sort(key=lambda t: t.get('minute', -1))
    del history[:-LIMIT]
    npc.flags['conversation_version'] = 2


def record(sim, npc, user='', reply='', medium='talk', turn_id=None):
    hydrate(sim, npc)
    history = npc.flags['conversation_history']
    turn_id = turn_id or new_id('turn')
    turn = next((t for t in history if t.get('id') == turn_id), None)
    if turn is None:
        turn = {'id': turn_id, 'user': user[:400], 'reply': '', 'medium': medium, 'minute': round(sim.minute, 2)}
        history.append(turn)
    if reply:
        turn['reply'] = reply[:1000]
    # Explicit player disclosures survive the rolling transcript. Store the
    # actual words, not AI-inferred facts or an invented biographical summary.
    if user and re.search(r"(?:^|[.!]\s+)(my |i am |i'm |i have |i've |i feel |i love |i hate |i work |i live |call me |don't call me |i prefer |i no |i dey )", user, re.I):
        notes = npc.flags.setdefault('conversation_notes', [])
        if user.casefold() not in {n['text'].casefold() for n in notes}:
            notes.append({'text': user[:400], 'medium': medium, 'minute': round(sim.minute, 2)})
        del notes[:-32]
    del history[:-LIMIT]
    return turn_id


def recall(npc, query):
    history = npc.flags.get('conversation_history', [])
    notes = npc.flags.get('conversation_notes', [])
    q = tokens(query)
    candidates = [(len(q & tokens(t.get('user', ''))), i, t) for i, t in enumerate(history)]
    hits = sorted((c for c in candidates if c[0]), reverse=True, key=lambda c: (c[0], c[1]))[:6]
    selected = {i for _, i, _ in hits} | set(range(max(0, len(history)-10), len(history)))
    lines = []
    for i in sorted(selected):
        t = history[i]
        lines.append(f"[{t.get('medium', 'talk')} at game minute {t.get('minute', 'legacy')}] Player: {t.get('user', '')}\nResident: {t.get('reply', '')}")
    relevant_notes = sorted(notes, key=lambda n: (len(q & tokens(n['text'])), n['minute']), reverse=True)[:10]
    if relevant_notes:
        lines.append('Player disclosures (quoted, not independently verified):\n' + '\n'.join(n['text'] for n in relevant_notes))
    plan = npc.flags.get('meeting')
    if plan:
        lines.append('Authoritative meeting state: ' + str({k: plan[k] for k in ('venue', 'due', 'status', 'wait_minutes') if k in plan}))
    return '\n'.join(lines)[-12500:]


def offline(npc, text, medium):
    history = npc.flags.get('conversation_history', [])
    q = tokens(text)
    # Recall only player statements, never confuse the NPC's words with facts
    # about the player. The current un-replied-to text is not a previous memory.
    if re.search(r'\b(remember|remind|what did i|what.*tell you|we discussed|we talked|you recall)\b|\b(what|where|when|who)\b.*\b(my|i told|i say|i work|i live)\b', text, re.I):
        candidates = [t for t in history if t.get('user') and t['user'] != text and '?' not in t['user']]
        candidates += [{'user': n['text'], 'medium': n['medium']} for n in npc.flags.get('conversation_notes', []) if n['text'] != text]
        if candidates:
            hit = max(enumerate(candidates), key=lambda pair: (len(q & tokens(pair[1]['user'])), pair[0]))[1]
            channel = {'text': 'text', 'call': 'our call', 'talk': 'when we spoke'}.get(hit.get('medium'), 'before')
            return f"I remember — you said “{hit['user']}” ({channel}). How did that go?"
        return "I don't remember that detail. Remind me small — I don't want to guess."
    # Ground common disclosures in their actual content instead of answering
    # an unrelated canned topic. Gemini can expand the same grounded context.
    if re.search(r'\b(interview|exam|lost my|bad day|tired|stressed)\b', text, re.I):
        if re.search(r'\b(passed|got the job|nailed|went well)\b', text, re.I):
            return "Ahh, that's good news! You actually did it 😂 How are you celebrating?"
        return "Eiya. That sounds like a lot. Tell me what happened — I'm listening."
    if re.search(r'\b(how far|how you dey|wetin dey|you dey okay|you dey alright)\b', text, re.I):
        return "I dey alright, just trying to finish today's wahala 😅 You nko?" if npc.stats.get('humor', 0) > .45 else "I'm alright o. Just a busy day. How you dey?"
    topics = {
        'nepa': ("Light has gone again? Omo, that can scatter somebody's plans. You have backup?", "Not NEPA choosing violence today 😭 Has it come back?"),
        'traffic': ("That traffic can test somebody's patience. Where are you stuck?", "Omo, road wahala again. Are you almost there or still inside it?"),
        'jollof': ("Now you're talking 😂 Who made it? Because not all jollof is equal o.", "Jollof sounds good right now. Party jollof or the one you cooked?"),
        'afrobeats': ("Which song? Send me the title, let me judge your taste small 😂", "Now that's a conversation. Who have you been listening to lately?"),
        'data': ("Data finishing at the wrong time is its own kind of heartbreak 😭 You sorted it?", "Omo. Were you in the middle of something when it finished?"),
        'birthday': ("Ah, birthday gist! What are you planning?", "So are we doing something small or are you going all out? 😂"),
    }
    for key, replies in topics.items():
        if re.search(r'\b' + key + r'\b', text, re.I):
            cursor = len(history) + int(npc.stats.get('humor', .5)*10)
            return replies[cursor % len(replies)]
    return None


def request_plan(sim, npc, text):
    """A reply here is a rule outcome: the model must not rewrite acceptance."""
    low = text.lower().replace('café', 'cafe')
    current = npc.flags.get('meeting')
    if re.search(r'\b(cancel|forget|never mind|nevermind)\b.*\b(meet|meeting|wait|plan|coming|hangout)\b', low):
        if current and current['status'] in ('scheduled', 'travelling', 'waiting'):
            current['status'] = 'cancelled'
            npc.target = None
            sim._npc_paths.pop(npc.id, None)
            npc.flags.pop('block_key', None)
            return "No wahala, I've cancelled our meetup. I'll carry on with my day."
        return "We don't have an active meetup to cancel."
    if re.search(r'\b(where|still|are you)\b.*\b(waiting|meeting|meetup)\b', low) and current:
        return f"Our meetup at {sim.location_names.get(current['venue'], current['venue'])} is {current['status']}."
    if not re.search(r'\b(wait for me|wait at|wait small|wait there|meet me|meet you at|see you at|meet up|meetup|come to|let.s meet|can we meet|make we meet)\b', low):
        return None
    from blxverse.content.locations import LOCATIONS
    aliases = {'cafe': ('cafe', 'coffee shop', 'two rivers'), 'restaurant': ('restaurant', 'saffron'),
               'park': ('park', 'juniper park'), 'square': ('square', 'town square')}
    matches = []
    for loc in LOCATIONS:
        names = (loc['id'].replace('_', ' '), loc['name'].lower(), *aliases.get(loc['id'], ()))
        if any(re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', low) for n in names):
            matches.append(loc['id'])
    venues = list(dict.fromkeys(matches))
    if len(venues) != 1:
        return "Where exactly should we meet? Give me one place, like the cafe, park or square."
    venue = venues[0]
    due = sim.minute
    delay = re.search(r'\bin (\d{1,3}) (minutes?|mins?|hours?|hrs?)\b', low)
    clock = re.search(r'\bat (\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\bat (\d{1,2}):(\d{2})\b', low)
    if delay:
        delta = int(delay[1]) * (60 if delay[2].startswith('h') else 1)
        if delta > 1440:
            return "Let's plan within the next day. What time works?"
        due += delta
    elif clock:
        hour, minute = int(clock[1] or clock[4]), int(clock[2] or clock[5] or 0)
        if minute > 59 or hour > (12 if clock[3] else 23) or (clock[3] and hour < 1):
            return "That time doesn't look right. Try something like at 6pm or at 18:30."
        if clock[3]:
            hour = hour % 12 + (12 if clock[3] == 'pm' else 0)
        due = int(sim.minute//1440)*1440 + hour*60 + minute
        if 'tomorrow' in low or due < sim.minute:
            due += 1440
    elif re.search(r'\b(tomorrow|tonight|later|next week|after work|in a few)\b|\bat \d', low):
        return "What time exactly? Say something like 'meet me at the park at 6pm'."
    loc = next(site for site in LOCATIONS if site['id'] == venue)
    opens, closes = loc.get('hours', [0, 24])
    if not opens <= (due % 1440)/60 < closes:
        return "That place is closed at that time. Pick another time or somewhere else?"
    rel = sim.rel(npc.id, 'player')
    block = sim._block_for(npc, (due % 1440)/60)
    if npc.status == 'sleeping' or npc.flags.get('hospital_until', 0) > sim.minute:
        return "I can't come out right now. Let's arrange another time."
    if rel.get('tension', 0) >= 55 or rel.get('familiarity', 0) < 8 or npc.mood.social_energy < 15:
        return "Not this time. I'm not comfortable making that plan right now."
    if block and block['kind'] in ('work', 'sleep'):
        return "I can't make that time — I've got work or rest scheduled. Pick another time?"
    from blxverse.engine.sim import find_path
    x, y = sim._npc_destination(npc, venue)
    path = find_path(npc.x, npc.y, x, y)
    if not path or ((path[-1][0]-x)**2+(path[-1][1]-y)**2)**.5 > 20:
        return "I can't find a clear way there right now. Let's pick another place."
    wait = re.search(r'\bfor (\d{1,3}) (minutes?|mins?)\b', low)
    duration = max(5, min(120, int(wait[1]))) if wait else 90
    plan = {'id': new_id('meet'), 'venue': venue, 'due': round(due, 2), 'status': 'scheduled',
            'wait_minutes': duration, 'x': x, 'y': y, 'created': sim.minute}
    npc.flags['meeting'] = plan
    name = sim.location_names.get(venue, venue)
    hh, mm = divmod(int(due)%1440, 60)
    day = int(due//1440)+1
    sim.note('Meetup agreed', f'{npc.first}: {name}, Day {day} {hh:02}:{mm:02}. Waiting up to {duration} game minutes after arrival.', 'social')
    return f"Okay, I'll meet you at {name}, Day {day} at {hh:02}:{mm:02}. I'll wait up to {duration} game minutes once I'm there. Don't keep me too long o 😅"


def meeting_step(sim, npc):
    p = npc.flags.get('meeting')
    if not p or p['status'] not in ('scheduled', 'travelling', 'waiting'):
        return False
    if sim.minute > p['due'] + 240:
        p['status'] = 'missed'
    elif p['status'] == 'waiting' and sim.minute >= p['wait_until']:
        p['status'] = 'finished'
        record(sim, npc, reply=f"I waited at {sim.location_names.get(p['venue'], p['venue'])} and have left now.", medium='meeting')
        sim.send_npc_message(npc.id, "I've left our meeting spot now. We can arrange another time.")
    else:
        if sim.minute < p['due'] - 60:
            return False
        if p['status'] == 'travelling' and not npc.target and npc.location_id == p['venue']:
            p['status'], p['wait_until'] = 'waiting', max(sim.minute, p['due']) + p['wait_minutes']
            record(sim, npc, reply=f"I'm at {sim.location_names.get(p['venue'], p['venue'])}, waiting for you.", medium='meeting')
            sim.send_npc_message(npc.id, "I'm at our meeting spot now. Let me know when you're here.")
        if p['status'] == 'waiting':
            npc.activity = 'waiting for your meetup'
            return True
        if p['status'] == 'scheduled' or not npc.target:
            npc.target = {'x': p['x'], 'y': p['y'], 'loc': p['venue'], 'activity': 'heading to your meetup', 'arrival_status': 'at', 'kind': 'meeting'}
            sim._npc_paths.pop(npc.id, None)
            npc.status, p['status'] = 'walking', 'travelling'
        return True
    npc.target = None
    npc.flags.pop('block_key', None)
    sim._npc_paths.pop(npc.id, None)
    return False
