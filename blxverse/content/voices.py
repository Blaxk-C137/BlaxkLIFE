"""Offline character voices. Authored parts compose on demand, not an LLM.

Capacity is a combinatorial slot count, NOT a claim of a million authored
stories. State-grounded answers and consent decisions always override a beat.
"""
from __future__ import annotations

from functools import lru_cache

from blxverse.engine.rng import stable_hash

# Identity is not inferred from gender/ethnicity. Named requested residents
# receive a deliberately different creative direction; the rest use archetypes.
NAMED_VIBES = {
    'Abdullahi': ('zen', 'The calm strategist', 'patience is a plan, not a delay'),
    'Smarty': ('gear', 'The curious analyst', 'every good question deserves a second question'),
    'Musty': ('zen', 'The laid-back storyteller', 'a slow afternoon is not a wasted afternoon'),
    'Legend': ('flame', 'The big-dream builder', 'start small, but never think small'),
    'Eboh': ('storm', 'The straight-talking creative', 'honest work beats a polished excuse'),
    'Joski': ('trickster', 'The friendly mischief-maker', 'make people laugh without making them the joke'),
    'Ofucks': ('trickster', 'The dry-wit night owl', 'not every notification deserves a reaction'),
    'Ysmanny': ('sprite', 'The playlist romantic', 'every ordinary day deserves a soundtrack'),
    'Samban': ('spark', 'The community spark', 'nobody should feel like a stranger twice'),
    'Fati': ('flame', 'The quietly fearless one', 'quiet does not mean unsure'),
    'Jenny': ('spark', 'The bright connector', 'introduce good people to good people'),
    'Omonu': ('gear', 'The observant realist', 'notice what people do, not only what they say'),
    'Elvina': ('sprite', 'The dreamy maker', 'leave a little room for the unexpected'),
}

# Eight genuinely different sentence rhythms, not a universal catchphrase.
OPENERS = {
    'spark': ('Ah, you!', 'Come closer.', 'Okay, listen.', 'You caught me smiling.', 'Good timing.', 'Now we can talk.', 'Well, hello there.', 'I like this interruption.'),
    'storm': ('Let me be clear.', 'Here is my take.', 'No grand speech today.', 'Honestly?', 'We can be real.', 'I will put it plainly.', 'I have thoughts.', 'Right, then.'),
    'zen': ('Take a breath.', 'No hurry.', 'I am listening.', 'A quiet thought:', 'Let us slow down.', 'One thing at a time.', 'We have a moment.', 'Softly, now.'),
    'gear': ('Interesting.', 'Let me think.', 'One observation:', 'I have a theory.', 'Small correction first.', 'Looking at it closely,', 'Here is the useful bit.', 'There is a pattern here.'),
    'flame': ('Here is the plan.', 'Straight to it.', 'Small steps count.', 'Keep this in mind.', 'My honest answer?', 'Let us make it count.', 'A little progress:', 'I am taking this seriously.'),
    'sprite': ('Picture this.', 'A little confession:', 'The odd thing is,', 'Stay with me.', 'There is a feeling here.', 'I keep thinking about it.', 'Maybe this sounds strange.', 'Let me find the words.'),
    'tank': ('Hey, good to see you.', 'You alright?', 'I have got a minute.', 'Come on, then.', 'Nothing fancy:', 'We can work with that.', 'Here, listen.', 'Glad you came by.'),
    'trickster': ('Plot twist:', 'For the record,', 'I have a tiny theory.', 'Before you blame me,', 'Unofficially speaking,', 'I will behave. Mostly.', 'No witnesses needed.', 'Between us, then.'),
}

STYLE_NOTES = {
    'spark': ('gathers people, shares little joys', '#f4ba64'),
    'storm': ('bold opinions, big gestures, direct answers', '#e88375'),
    'zen': ('unhurried words, careful listening, dry warmth', '#8bc7ae'),
    'gear': ('notices details, asks why, thinks out loud', '#83b9df'),
    'flame': ('focused plans, high standards, quiet ambition', '#e4ae68'),
    'sprite': ('images, music, small things made meaningful', '#c1a5e3'),
    'tank': ('steady warmth, practical help, easy humour', '#9db97b'),
    'trickster': ('sideways jokes, curious energy, a softer centre', '#d4a7bb'),
}

# Eight new intent-specific beats each, alongside the original archetype banks.
BEATS = {
 'greeting': (
    'Hey, {player}. You found me at {venue}.', 'Hello! I was just thinking about {topic}.',
    'There you are, {player}. How is your corner of BlaxkVille?', 'A familiar face makes {venue} better.',
    'Hey. I can pause the day for a proper hello.', 'Good to see you without a screen between us.',
    'Hello, neighbour. What is on your mind?', 'Welcome to my small interruption of the day, {player}.'),
 'how_are_you': (
    'I am feeling {mood}, if we are being honest.', 'Today is a {mood} kind of day for me.',
    'Trying to {goal}. That is the honest update.', 'Somewhere between {mood} and needing a snack.',
    'I am keeping an eye on my energy. Right now: {mood}.', 'Thanks for asking rather than guessing. I feel {mood}.',
    'My head is on {goal} today.', 'I have {activity} on my plate. One thing at a time.'),
 'smalltalk': (
    'I could talk about {topic} for longer than is sensible.', 'BlaxkVille makes an ordinary walk feel like a chapter.',
    'I am trying to {goal}; even tiny progress counts.', 'There is always something to notice at {venue}.',
    'My current activity is {activity}, not saving the universe.', 'I keep coming back to {topic}.',
    'It is nice to have a conversation with no urgent announcement.', 'I would rather hear your actual day than a perfect version of it.'),
 'joke': (
    'My calendar has started scheduling breaks from my breaks.', 'The fountain has more reliable plans than I do.',
    'I called my to-do list a rough draft. It took that personally.', 'I went for a short walk and returned with three opinions.',
    'I tried being mysterious. Everyone assumed I needed directions.', 'The market receipt is now my longest published work.',
    'My hobby is collecting hobbies I will definitely start next week.', 'I have excellent timing, usually five minutes after it is needed.'),
 'compliment': (
    'Thank you. It is nice when the effort is seen.', 'That is kind, {player}. I will take the compliment without arguing.',
    'You noticed? That genuinely means something.', 'I was not sure anyone would notice. Thank you.',
    'That landed better than you probably intended.', 'I will remember that on a less confident day.',
    'You have a way of making a small moment better.', 'I appreciate a specific compliment. It feels real.'),
 'flirt': (
    'Let us get to know each other rather than rushing this.', 'I hear you, but I still get to set my own pace.',
    'You are being charming. I am still deciding how I feel.', 'A little chemistry is not the same as a promise.',
    'I would rather be understood than swept off my feet.', 'You have my attention, not a blank cheque.',
    'We can enjoy the moment without inventing the ending.', 'Keep it kind, {player}. That matters to me.'),
 'ask_date': (
    'Ask me about a real plan and I will give you a real answer.', 'I like a clear invitation, not an assumption.',
    'A date should feel good for both of us.', 'Tell me the plan and let me decide.',
    'I would rather choose honestly than say yes out of politeness.', 'Timing and trust matter as much as the venue.',
    'An invitation is a question, not a reservation.', 'Let us not skip the part where we know each other.'),
 'gift': (
    'You thought of me when you saw {item}? That is a sweet detail.', 'I always notice the thought behind a gift.',
    'Thank you for bringing something, {player}.', 'A gift tells me what somebody has noticed about me.',
    'You did not have to bring anything to have my attention.', 'I care more about meaning than a price tag.',
    'I will give you an honest reaction, not a rehearsed one.', 'That was a thoughtful interruption of an ordinary day.'),
 'gossip': (
    'What did you actually see, and what did somebody add?', 'A rumour is not the same thing as a receipt.',
    'I am interested, but I will not call a guess a fact.', 'BlaxkVille is small. Words travel faster than people.',
    'Let us ask before we decide who the villain is.', 'I would like the part of the story with evidence.',
    'Somebody being quiet is not proof of anything.', 'There is usually a less dramatic explanation.'),
 'invite': (
    'Tell me when and where; I need to check my own plans.', 'An invitation is nice. A surprise obligation is not.',
    'I like the idea of making time, not just saying we should.', 'Let us choose something we would both enjoy.',
    'I am interested in the plan, not the pressure.', 'Keep it simple and give me room to answer.',
    'I would rather do one good thing than rush through five.', 'What did you have in mind at {venue}?'),
 'apology': (
    'I hear the apology. What happens next matters too.', 'Thank you for saying it plainly.',
    'We can take a step forward without pretending nothing happened.', 'I need honesty more than a perfect speech.',
    'An apology can start the repair, not finish it for us.', 'I am listening. I still need my boundaries respected.',
    'Let us not keep making the same hurt into a routine.', 'I appreciate you coming back to the conversation.'),
 'insult': (
    'That is not how I want to be spoken to.', 'We can disagree without you trying to cut me down.',
    'I am not a target for your bad day.', 'Stop there. That crossed a line for me.',
    'If you want a conversation, speak to me with respect.', 'No. I am not laughing that off.',
    'You can be upset without being cruel.', 'I will step away if this is how the conversation is going.'),
 'deep': (
    'I want to {long_goal}, even if it takes longer than I planned.', 'I have been trying to {goal}. It is not always easy.',
    'Some days being honest takes more courage than being impressive.', 'I am learning that a quiet life can still be a full one.',
    'I care about {value}; that shapes more choices than people notice.', 'I do not want to confuse being busy with being fulfilled.',
    'Trust grows in the small things people actually follow through on.', 'I would like to be understood without having to perform.'),
 'goodbye': (
    'Take care, {player}. We will catch up another time.', 'Go well. I have {activity} to get back to.',
    'See you around {venue}. No need to rush back.', 'Thanks for stopping rather than just waving.',
    'I will let you get on with your day.', 'We can leave the conversation on a good note.',
    'Catch you later, neighbour. Look after yourself.', 'Until next time. BlaxkVille will keep us busy.'),
 'ask_about': (
    'I am {name}, a {job}, and more than the job title.', 'My hobbies include {hobby}. That is usually a good place to start.',
    'I care about {value}. You learn a lot about me from that.', 'The big dream is to {long_goal}.',
    'I have a soft spot for {food} and {music}.', 'My small goal right now is to {goal}.',
    'You can usually find me thinking about {topic}.', 'I would rather introduce myself through a conversation than a list of facts.'),
 'fallback': (
    'I am not quite sure what you mean. Could you put it another way?', 'I heard you, but I do not want to pretend I understood.',
    'Help me connect that to what we were talking about.', 'I might be missing the point. What matters most in that?',
    'Tell me a little more, {player}.', 'I can listen, but I cannot read your mind.',
    'Are you asking about me, or about something happening here?', 'Let us take that one thought at a time.'),
}

# 10 factual personal fragments x 10 framings = 100 per resident. No invented
# past events, relationships, achievements, bookings, or secret revelations.
FACT_FRAMES = (
    'For me, {fact}.', 'One thing about me: {fact}.', 'If you want the honest version, {fact}.',
    'This is very much my thing: {fact}.', 'A small detail that matters to me: {fact}.',
    'Something I keep coming back to: {fact}.', 'Behind all the noise, {fact}.',
    'Here is the personal bit: {fact}.', 'Off the top of my head, {fact}.',
    'Away from the small talk, {fact}.',
)
FOLLOWUPS = (
    'What about you?', 'What has your day been like?', 'What is on your mind?', 'I am happy to listen.',
    'Tell me your version.', 'No pressure to have a perfect answer.', 'We can keep this simple.', 'What matters to you in that?',
    'How do you see it?', 'I have time for an honest answer.', 'There is no rush.', 'What would you do differently?',
    'That is where my head is today.', 'I would like to hear your take.', 'We do not have to agree on everything.', 'Your turn, if you want.',
    'What would make today a little better for you?', 'I am curious what you noticed.',
    'Tell me if I am looking at this the wrong way.', 'What are you looking forward to?',
)


@lru_cache(maxsize=256)
def voice_identity(first: str, npc_id: str, archetype: str) -> dict:
    style, label, motto = NAMED_VIBES.get(first, (archetype, '', ''))
    if style not in OPENERS:
        style = 'spark'
    note, color = STYLE_NOTES[style]
    if not label:
        modifiers = ('Reflective', 'Playful', 'Restless', 'Thoughtful', 'Low-key', 'Expressive', 'Warm', 'Independent')
        label = f"{modifiers[stable_hash('vibe', npc_id) % len(modifiers)]} {style}"
    return {'style': style, 'label': label, 'description': note, 'motto': motto, 'color': color,
            'signature': f'{first} · {label}'}


def identity(npc) -> dict:
    return voice_identity(npc.first, npc.id, npc.archetype)


def personal_facts(npc) -> tuple[str, ...]:
    voice = identity(npc)
    hobby = npc.hobbies[0] if npc.hobbies else 'watching the neighbourhood'
    second = npc.hobbies[-1] if npc.hobbies else 'quiet walks'
    return (
        f'{hobby} is one of my favourite ways to spend time',
        f'I have a soft spot for {npc.favorite_food}',
        f'{npc.favorite_music} is my kind of music',
        f'I want to {npc.goal_short}',
        f'the bigger dream is to {npc.goal_long}',
        f'{npc.values[0] if npc.values else "kindness"} matters to me',
        f'I am interested in {second} as well as my work',
        f'my work as a {npc.occupation} is only one part of me',
        voice['motto'] or f'people know me as the one who {npc.quirk}',
        f'I am {npc.first}, and I would rather have a real conversation than a perfect one',
    )


def variant_indices(npc, seed: int, intent: str, turn: int, core_count: int) -> tuple[int, int, int, int]:
    """A full-period mixed-radix deck; cursor lives in NPC flags, not in RAM RNG."""
    total = core_count * 8 * 100 * 20
    # 7919 is prime and coprime to all current radix factors (8..32 cores).
    from math import gcd
    step = 7919
    while gcd(step, total) != 1:
        step += 2
    n = (stable_hash('voice-deck', seed, npc.id, npc.first, intent) + turn * step) % total
    out = []
    for radix in (core_count, 8, 100, 20):
        out.append(n % radix)
        n //= radix
    return tuple(out)


def dress_reply(npc, core: str, indices: tuple[int, int, int, int], intent: str) -> str:
    _, opening, detail, closing = indices
    voice = identity(npc)
    # Sensitive / outcome-bearing turns never pivot into cheerful small talk.
    if intent in ('insult', 'apology', 'flirt', 'ask_date', 'gift', 'goodbye', 'gossip'):
        return f"{OPENERS[voice['style']][opening]} {core}"
    fact = personal_facts(npc)[detail % 10]
    aside = FACT_FRAMES[detail // 10].format(fact=fact)
    return f"{OPENERS[voice['style']][opening]} {core} {aside} {FOLLOWUPS[closing]}"


def nominal_capacity(npc) -> int:
    # A conservative slot count using only the eight NEW beats per intent.
    # Actual questions may collapse core slots to a state-grounded answer;
    # boundary-sensitive intents deliberately use fewer fragments at runtime.
    return sum(len(v) * 8 * 100 * 20 for k, v in BEATS.items() if k not in
               ('insult', 'apology', 'flirt', 'ask_date', 'gift', 'goodbye', 'gossip'))
