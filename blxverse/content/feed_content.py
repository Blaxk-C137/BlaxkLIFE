"""Social feed and message content banks.

Posts are written to sound like residents, not like a content generator.
They reference hobbies, moods, venues and small neighborhood details.
"""

from __future__ import annotations

POST_TEMPLATES = {
    "morning": [
        "Morning from {venue}. The light is doing that golden thing again. I'm pretending it's for me. ☀️",
        "Two coffees in and I've already said 'let's circle back' to a person who did not deserve it.",
        "The early shift is a personality. Mine. Unfortunately.",
        "If you heard someone singing badly near {venue}, that was me practicing joy.",
    ],
    "work": [
        "Customer at work asked if we sell 'the usual'. Sir. We have never met. But I respect the confidence.",
        "Four hours into my shift and the espresso machine and I have reached an understanding. It's fear.",
        "Today at work I fixed something with a spoon. I will not be taking questions.",
        "My boss said 'quick question'. Reader, it was not quick, and it was barely a question.",
    ],
    "food": [
        "Someone at {venue} put {food} in front of me and honestly? I blacked out. 10/10.",
        "I will not be taking criticism on how much of this {food} I can eat. This is a lifestyle.",
        "Cooked something ambitious. It's either dinner or a science experiment. Updates to follow.",
    ],
    "evening": [
        "Evening at {venue} with zero plans and a full playlist. This is the good stuff.",
        "The block is loud in the good way tonight. Someone is laughing two streets over. Hope it's on purpose.",
        "Quiet night in. I have snacks, a blanket, and a vague sense that I should text someone back. Later.",
    ],
    "music": [
        "Found a {music} record at Vinyl Corner. The cat judged me. The cat was right. Still buying it.",
        "'Just one more song' is a lie I tell myself every single night. Currently on song six.",
        "Somebody played {music} out of a car window today and the whole street improved.",
    ],
    "friends": [
        "Ran into {friend} at {venue}. Ended up talking for an hour about absolutely nothing important. Best hour of the week.",
        "The group chat is on fire about the correct way to hang a picture. This is the discourse I signed up for.",
        "{friend} owes me a coffee and I intend to collect with interest.",
    ],
    "mood_low": [
        "Not every day is a highlight reel. Today I'm moving slowly and being gentle with myself. That's it.",
        "I was going to be productive. Instead I stared at the ceiling and thought about the ocean. Balance.",
        "Small sad today. Gonna walk to the park and let the pigeons fix it.",
    ],
    "mood_high": [
        "No specific reason, but today is good. The air is good. The sidewalk is good. Everything is doing great.",
        "I laughed so hard at nothing that a stranger checked if I was okay. I am. More than okay.",
        "Today I did one small brave thing and I'm going to be smug about it for 48 hours.",
    ],
    "complaint": [
        "Whoever left a shopping trolley in the middle of the sidewalk: I know what you did and so does the entire block. Hope you sleep well. 😤",
        "The playlist at {venue} has been the same three songs for forty minutes. I'm starting a formal inquiry.",
        "A pigeon has decided my balcony is its office. We had a meeting. It's staying. I'm the assistant now.",
    ],
    "love": [
        "There's a person who makes {venue} feel like a better place and I refuse to elaborate further. 💛",
        "The barista drew a heart on my cup. It was probably accidental. I'm choosing to believe it wasn't.",
        "I think the bravest thing in the world is being honest about what you want. Working on it.",
    ],
}

ARCHETYPE_POSTS = {
    "spark": [
        "Public service announcement: the mango cake at {venue} is back. I cried a little. That's community.",
        "I know everyone on this block and I've just learned something about someone that contradicts everything. The newsletter is coming.",
        "Group chat update: twelve people are coming, nobody knows what to bring, and I have made a spreadsheet. This is leadership, actually.",
    ],
    "storm": [
        "Today I experienced a minor inconvenience and have since decided to treat it as a personal plot arc.",
        "I gave a speech at a table of four people at {venue}. They were captive and I was magnificent.",
        "Somebody said I'm 'a lot'. Yes. And? Continue.",
    ],
    "zen": [
        "Walked to {venue} without music today. Heard six birds and one terrible scooter. Recommended.",
        "Reminder to breathe before replying. I did this. I still replied badly. But I breathed first.",
        "If you're having a loud day, the park benches at dusk are basically a reset button.",
    ],
    "gear": [
        "Spent 40 minutes explaining why the card reader fails to someone who did not ask. Growth.",
        "I have three tabs open about the same topic. They disagree. So do I. This is research, not confusion.",
        "The shop's spreadsheet now has a colour for every mood of customer. I'm told this is 'too much'. It's precise.",
    ],
    "flame": [
        "Wrote my plan for the next quarter on a napkin at {venue}. This napkin is basically a legal document now.",
        "Reminder: rest is part of the plan. I've scheduled it. It felt illegal. I'm doing it anyway.",
        "You don't need permission to start small. You need a spreadsheet. Obviously both. 📈",
    ],
    "sprite": [
        "Wrote half a song about the light at {venue}. It's about the light, and also not about the light.",
        "There's a particular way the street looks after rain. I'm going to spend my whole day thinking about it. Sorry in advance.",
        "Played something new to an audience of one pigeon. The pigeon stayed for the whole thing. That's a review.",
    ],
    "tank": [
        "Gym at six, then I carried three bags of groceries for a neighbor I've never met. Good day so far. 💪",
        "I don't need a reason to be excited about today. But I have three. Snacks are two of them.",
        "If you see me at {venue} pretending I'm not dancing, you're correct but you can't prove it.",
    ],
    "trickster": [
        "I did a harmless prank today and the wrong person got it. The person was me. It was still funny.",
        "Somebody's garden gnome is on vacation. That's all I'm saying. It has a hat.",
        "I've been told I need to apologise for the whoopee cushion situation. I'd like to apologise. In person. With a whoopee cushion. 😇",
    ],
}

POST_BY_LOCATION = {
    "cafe": "At Two Rivers Cafe. If you need me, I'm the one pretending my coffee is a personality.",
    "park": "Juniper Park update: the swings are still the best invention ever made. I'm an adult. I'm aware.",
    "grocery": "Market run. I came for tomatoes, I'm leaving with three kinds of bread and a new friend.",
    "gym": "The Junkyard Gym smells like ambition and old chalk. Wouldn't change a thing.",
    "cinema": "Starlite Cinema tonight. The seats lean back and the butter is unhinged. Fine with both.",
    "restaurant": "Saffron & Smoke. Ordered dessert first. This is not a mistake, it's a philosophy.",
    "studio": "Golden Hour Studio. The booth is dusty, the dreams are not.",
    "clothing": "Neon Threads. The mirror has seen me try four jackets. It's keeping notes.",
    "music_store": "Vinyl Corner. The cat has opinions and I'm taking them personally.",
    "salon": "The Glow Room. Someone's haircut is good and it's mine. 💇",
    "square": "BlaxkVille Square. Best place to sit and invent stories about people who are just buying fruit.",
}

COMMENT_TEMPLATES = [
    "Okay this is extremely valid.",
    "😭😭😭 you can't just say that in public",
    "Saw this coming and said nothing. My fault.",
    "I am on my way. Save me a seat.",
    "This is the most accurate thing posted on this app today.",
    "Careful, the group chat has screenshots.",
    "You're doing way better than you think.",
    "I'll pretend I didn't see this and bring it up at dinner.",
    "The block is talking. Love that for us.",
    "Supportive, but also: what?",
    "Next time invite me. I have a car and opinions.",
    "I needed this today. Genuinely.",
]

MESSAGE_TEMPLATES = {
    "spark": [
        "Okay quick question. If you had to pick: mango cake at {venue} or {food}? This is urgent and also not urgent at all.",
        "So I heard something and I'm trying very hard not to be the person who repeats it immediately. This is me, trying. 😬",
        "Are you okay? I saw you earlier and you had That Look. I'm asking as a friend who definitely isn't making it weird.",
        "The group chat is planning something and I need you to be there so I'm not the most enthusiastic one. That spot is yours.",
    ],
    "storm": [
        "I need to tell you about a thing that happened. It has three acts and an intermission. Call me?",
        "FYI someone is being weird about you-know-what. I'm handling it. Dramatically, but handling it.",
        "You missed a scene at {venue}. I was magnificent, then humble, then magnificent again.",
    ],
    "zen": [
        "Hey. No agenda. Just wanted to check in. Hope your day's been gentle.",
        "Saw something at {venue} that made me think of you. Putting it in the album of things to share later.",
        "If you're free later and want quiet company, the park is good around dusk.",
    ],
    "gear": [
        "Hey — quick question when you get a sec. Not urgent. Okay mildly urgent. Very urgent.",
        "I found an article about something we talked about. Sending it even though you didn't ask.",
        "Are you free later? I want to test a theory about the cafe's playlist on someone reasonable.",
    ],
    "flame": [
        "I'm putting together a plan. You're in it. I'll explain, but you should know the plan exists.",
        "Quick professional question, and also a personal one. They're kind of the same thing. Call me.",
        "Did a lot of thinking at {venue}. I want to run something by you soon.",
    ],
    "sprite": [
        "I wrote something and I'm scared to show you but you're the only one I want to show. No pressure. Okay pressure.",
        "The fountain is doing the thing it does in the evening. I thought you might want to know it's still doing that.",
        "Hey. Random. Thank you for being a person I can be weird around.",
    ],
    "tank": [
        "Hey buddy! Got two tickets to the cinema and need one more person. The movie might be bad. Snacks will be good.",
        "I'm at the gym and the playlist is unhinged. Thinking of you. In a normal way. Mostly.",
        "You ate lunch yet? I'm asking seriously. I will know if you lie.",
    ],
    "trickster": [
        "Don't be alarmed but don't check your shoes immediately either. It's a riddle, it's also a warning, it's also fine.",
        "I'm bored and I have a plan. You should be concerned. You should also come to the park.",
        "Someone saw me being nice and now I have to restore balance. Help me plan a small bit.",
    ],
}

MESSAGE_FOLLOWUPS = [
    "Also I'm not ignoring your last message, I'm rereading it. It's long. I love that. Reply soon.",
    "Okay, actually, ignore all that. How are you?",
    "That was a lot. I'm going to go lie on the floor for a bit. Text you later.",
]

MISSED_CALL_LINES = {
    "spark": "Hey! Missed you — call me back? I have news and it's 70% about cake.",
    "storm": "You missed my call. I had a monologue. It's gone now. Call me for the rerun.",
    "zen": "No worries if you're busy. I just called to hear how you are.",
    "gear": "Missed you. Nothing urgent. Just had a thought you'd enjoy.",
    "flame": "Tried you. No emergency — just a thought I'd rather say out loud.",
    "sprite": "I called and wrote half a song while it rang. Call me back when you can.",
    "tank": "Hey! Call me back when you're free. Snack-related news.",
    "trickster": "Missed you. That's the whole message. No prank. This time.",
}
