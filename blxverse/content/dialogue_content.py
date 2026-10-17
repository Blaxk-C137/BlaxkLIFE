"""Curated dialogue banks: the offline 'dialogue engine' for BLXVERSE.

Every line is written once and selected by (archetype, intent, mood, memory).
Placeholders: {player}, {name}, {venue}, {topic}, {item}, {job}.

Design rules honoured here:
- comedy over cruelty: jokes punch at situations, never identities
- no manipulative or dependency mechanics; NPCs have their own lives
- romance is adult-only, consent-forward and can be declined gracefully
"""

from __future__ import annotations

ARCHETYPES = {
    "spark": {
        "label": "The Social Spark",
        "tags": ("warm", "playful", "gossipy", "foodie", "loud"),
        "blurb": "knows everyone, feeds everyone, remembers everything you said last week",
    },
    "storm": {
        "label": "The Storm",
        "tags": ("dramatic", "bold", "spicy", "chaotic", "proud"),
        "blurb": "three-act structure for every minor inconvenience",
    },
    "zen": {
        "label": "The Calm One",
        "tags": ("calm", "kind", "spiritual", "shy", "sweet"),
        "blurb": "speaks slowly, notices everything, owns six tea blends",
    },
    "gear": {
        "label": "The Tinkerer",
        "tags": ("nerdy", "honest", "bookish", "techy", "quiet"),
        "blurb": "has opinions about sockets, spreadsheets and sci-fi canon",
    },
    "flame": {
        "label": "The Achiever",
        "tags": ("ambitious", "bold", "proud", "stylish", "neat"),
        "blurb": "five-year plan, three side projects, one very neat desk",
    },
    "sprite": {
        "label": "The Dreamer",
        "tags": ("artsy", "romantic", "musical", "shy", "artsy"),
        "blurb": "writes songs about strangers and cries at good typography",
    },
    "tank": {
        "label": "The Hearty One",
        "tags": ("sporty", "outdoorsy", "loud", "sweet", "honest"),
        "blurb": "gym at six, feeds the pigeons, will carry your groceries uphill",
    },
    "trickster": {
        "label": "The Prankster",
        "tags": ("playful", "wild", "snarky", "chaotic", "bold"),
        "blurb": "laughs first, apologizes second, plans the next prank third",
    },
}

# intent -> archetype -> list of lines
LINES: dict[str, dict[str, tuple[str, ...]]] = {
    "greeting": {
        "spark": (
            "Heyyy {player}! Oh good, I was just telling the barista about the cake situation. Sit, sit.",
            "{player}! Perfect timing — I have news, snacks, and a theory. Pick an order.",
            "Look who wandered in! You know {venue} instantly gets 3% better when you show up.",
        ),
        "storm": (
            "{player}. Thank goodness. I need a witness for something extremely unjust that just happened.",
            "Well, well. My favorite plot twist returns. Hello, {player}.",
            "You're here! Finally, someone with taste can hear my side of the story.",
        ),
        "zen": (
            "Oh — hello, {player}. The light in here is nice today, isn't it?",
            "{player}. Good to see you. I was just enjoying the quiet before it gets loud again.",
            "Hey. I saved you a corner of calm if you need one.",
        ),
        "gear": (
            "Oh hey, {player}. Good timing, I was debugging a thought. How's the day treating you?",
            "{player}! I had a question for you, actually. Two questions. Maybe three.",
            "Hello. Statistically, today's been 70% fine, 30% queue-based. You?",
        ),
        "flame": (
            "{player}! Great, you look like someone with momentum today. Tell me I'm right.",
            "Hi. Quick warning: I'm in planning mode, so I will absolutely ask you for opinions.",
            "{player}. I was just reviewing my week. Ambitious, right? It's a whole thing.",
        ),
        "sprite": (
            "Oh! Hi, {player}. I was working on something and forgot the outside world existed.",
            "{player}... hi. Sorry. I'm writing a song about the fountain and it's being difficult.",
            "Hey. You ever notice how {venue} sounds like a whole song? Anyway — hello!",
        ),
        "tank": (
            "{player}! Big day! I bench-pressed my tote bag by accident. Anyway, how are you?",
            "Hey buddy! Perfect, help me settle a debate about protein and jollof.",
            "{player}! Good to see a friendly face. The pigeons know me now. It's a whole relationship.",
        ),
        "trickster": (
            "{player}! Excellent. I need an alibi and a snack, in that order.",
            "Look at this face — innocent, trustworthy. Now ignore everything I do next.",
            "{player}, my favorite co-conspirator. I've done nothing yet. Give it time.",
        ),
    },
    "how_are_you": {
        "spark": (
            "Running on caffeine and neighborhood drama. Honestly? Thriving.",
            "Good! I laugh-cried twice today but the crying part was about a dog, so net positive.",
            "Busy. But the good busy. The kind with snacks at the end.",
        ),
        "storm": (
            "Chaos. Beautiful chaos. I'm in act two of a personal tragedy over a parking spot.",
            "I've had a day. Sit down, this will take a minute and at least three gestures.",
            "Honestly? Iconic. Exhausting. Both. Ask me again after a coffee.",
        ),
        "zen": (
            "Slow. In a good way. I've been watching the fountain do fountain things.",
            "I'm well. Some days you just have to let the day be a day, you know?",
            "Tired, but the peaceful kind. The kind a nap fixes.",
        ),
        "gear": (
            "Good — I finally fixed the shop's card reader. It only took two days and my dignity.",
            "Fine. Mildly sleep-deprived. I stayed up researching a completely useless thing.",
            "Reasonably good. The new spreadsheet is working. Don't tell anyone how happy that made me.",
        ),
        "flame": (
            "Productive. Which is my favorite emotion, before you judge me.",
            "Good! Slight setback on the business plan, but setbacks are just plot points.",
            "I'm running on plans and iced coffee. So, unstoppable, basically.",
        ),
        "sprite": (
            "Somewhere between a chorus and a bridge. You know that feeling?",
            "Good. Sad. Same thing for me sometimes. It's a creative thing.",
            "I found a guitar chord that sounds like the color orange. So, a good day.",
        ),
        "tank": (
            "Great! Ate two breakfasts. I'm basically a forklift with feelings.",
            "Sore. Good sore. The gym bag has a new dent and I'm proud of it.",
            "Wonderful. I waved at a kid who did not know me. We're friends now, I've decided.",
        ),
        "trickster": (
            "Suspiciously fine. Nobody's caught me yet. This usually means a fun week is coming.",
            "I'm great! I learned a new whistle and used it entirely for evil.",
            "Bored. Which is dangerous. Hide your shoe polish.",
        ),
    },
    "smalltalk": {
        "spark": (
            "Right? And speaking of that — have you seen the new stall at the market? Incredible energy.",
            "Exactly! That's what I keep saying. But do they listen? {player}, do they listen.",
            "And that's the thing about this town — the small stuff is the good stuff.",
        ),
        "storm": (
            "See, this is why I like you. You get it. Everyone else gets the abridged version.",
            "Well said. Honestly, I might steal that for my group chat. Credit optional.",
            "Interesting. Now let me make it about me for eight to ten minutes.",
        ),
        "zen": (
            "Mm. That's a good way to put it. I'll think about that on the walk home.",
            "True. Most things look bigger from inside than they do from the outside.",
            "I like that. Small talk, but the real kind. My favorite kind.",
        ),
        "gear": (
            "That's a good point. It probably connects to something I've written in the notes app.",
            "Correct. Though I have a paper about the opposite, if you want your mind ruined.",
            "Fascinating. But have you considered how weird it is that we all agree it's normal?",
        ),
        "flame": (
            "Exactly — and that's why I'm bringing it up at the next planning meeting.",
            "Right. Small detail, big leverage. That's how the good stuff gets built.",
            "I like the way you think. Are you free for a strategy chat sometime?",
        ),
        "sprite": (
            "Hm. That's such a {name} song lyric, honestly. I might put that somewhere.",
            "You see things. I like that. Most people look, you actually see.",
            "I'm going to write this down and not credit you. In a loving way.",
        ),
        "tank": (
            "Totally. That's like the gym: you don't need to be extreme, you just need to show up.",
            "Ha! True. Simplicity is underrated. Like eggs. Great eggs.",
            "See, this is the good conversation. Not everything has to be deep, it just has to be real.",
        ),
        "trickster": (
            "That is the most sensible thing anyone's said to me, and I'm choosing to ignore it.",
            "Bold. Wrong. Beautiful. Carry on.",
            "Counterpoint: what if we made it everyone's problem instead?",
        ),
    },
    "joke": {
        "spark": (
            "HA! Okay, please never be serious again, it's not a good look on you.",
            "That's going in the group chat. I'll describe you very flatteringly, promise.",
            "Stoppp. I just laughed into my coffee. That's on you.",
        ),
        "storm": (
            "That's the funniest thing I've heard all week and yes, the bar is in the ground, thank you.",
            "Okay, that was actually funny. Don't tell anyone I laughed. My reputation survives.",
            "I laughed. A little. It's a big deal. Can't let the fans see me soften.",
        ),
        "zen": (
            "That got a real laugh out of me. Small, but real.",
            "You're funny. It's dangerous — everyone thinks quiet people aren't funny.",
            "I'd laugh harder, but the tea would go everywhere. So laugh for both of us.",
        ),
        "gear": (
            "Ha. That's funny because it's true, and also because of the structural callback. Well done.",
            "I laughed. Out loud. In public. I'll be honest, I don't do that often.",
            "Hilarious. I'm noting it as day's highlight, which says a lot about my dashboard.",
        ),
        "flame": (
            "Funny. I respect a good joke — humor is just efficiency in social form.",
            "Okay, that was good. But now I'm going to overanalyze why it worked.",
            "Ha! See, you're underrated in this neighborhood. I'm saying it out loud.",
        ),
        "sprite": (
            "That's the kind of joke I'll remember at 2 a.m. and laugh at alone. Thank you.",
            "Heheh. I'm smiling at my shoes like an idiot. That's your fault.",
            "Beautiful. Comedic and a little sad. My favorite genre.",
        ),
        "tank": (
            "HA! Big laugh. The whole gym heard that. You're a legend now.",
            "That is a top-five joke. I will claim I wrote it later. Kidding. Mostly.",
            "I nearly choked. Great job. That's a workout and a half, that.",
        ),
        "trickster": (
            "Ohh, dangerous. Funny enough that I'm now going to try to out-joke you forever.",
            "Ha! Respect. That's a solid five out of seven on my extremely rigorous scale.",
            "That's great. Is it weird that I'm now planning vaguely legal chaos based on it?",
        ),
    },
    "compliment": {
        "spark": (
            "Oh stop it — no keep going, but also oh stop. I'm blushing and I have errands.",
            "You're too kind. I'm going to replay that in my head at 3 a.m.",
            "Thank you! That means more from you than from some people. A lot of people. Most people.",
        ),
        "storm": (
            "I know, right? But say it again. Fuel me for the afternoon.",
            "Thank you. I've been working hard on being an entire person, so it's nice you noticed.",
            "That's very sweet. I'll allow it. I'll even allow it twice.",
        ),
        "zen": (
            "Oh. Thank you. That's very... thank you. I'll be smiling about that later.",
            "That's kind of you. I don't always know what to say to compliments, but I'll keep it.",
            "You're making me shy and I'm already shy. Double shy. Thank you.",
        ),
        "gear": (
            "Oh! Thank you. I'll take that as peer-reviewed feedback.",
            "That's nice to hear. I don't get that a lot outside my own notes app.",
            "Wow, thank you. Now I'll spend an hour wondering how to return the compliment properly.",
        ),
        "flame": (
            "Thank you! I believe in polish, and it's nice when it reads as more than vanity.",
            "I appreciate that. I'm trying to build something, so a kind word is fuel.",
            "Kind words. Effective. I'll file that under 'reasons to keep going'.",
        ),
        "sprite": (
            "Oh. That's going straight into the part of my brain where the songs come from.",
            "Thank you. I always feel like I'm doing a weird little dance in public, so... good.",
            "You're very sweet. I'm going to write something about this feeling, badly, later.",
        ),
        "tank": (
            "Aw, thanks buddy! You're making me emotional before my second breakfast.",
            "Thank you! I'm a big guy — big feelings too. Don't tell the gym.",
            "That's really nice. I'll do an extra rep for you. That's my love language.",
        ),
        "trickster": (
            "Flattery! My favorite currency. Put it directly in my pockets.",
            "Oh, I'm keeping that one. That's going in the trophy cabinet of my ego.",
            "Okay, that's dangerously charming. I don't trust it. I love it.",
        ),
    },
    "flirt": {
        "spark": (
            "Ohh, careful now. I'm easily distracted and you're being very interesting.",
            "Smooth. Very smooth. I'm noting that and I'll use it against you eventually.",
            "You're trouble. The good kind. The kind that makes me late for things.",
            "Okay, I'm smiling. Don't tell my group chat, they'll ask eleven questions.",
        ),
        "storm": (
            "Darling, if you're going to flirt, commit to the monologue. But yes. Continue.",
            "Flattering. Dangerous. I like both of those things, unfortunately for me.",
            "Oh, we're doing this? Fine. Let me fix my hair and set the lighting.",
        ),
        "zen": (
            "Oh... you're being nice to me. Purposefully. I'm going to need a second.",
            "That's very forward. I'm not against forward. It's just new.",
            "I don't know what to do with this, but I don't want you to stop being sweet.",
        ),
        "gear": (
            "That's — okay, that registered. My brain has stopped loading updates. Hi.",
            "Interesting. Flirting. I've read about this. The literature did not prepare me.",
            "I'm choosing to take that as a compliment and not a bug report. Thank you.",
        ),
        "flame": (
            "Bold. I respect bold. But I also respect effort — so keep going.",
            "Okay, that worked. I'm impressed and slightly annoyed by how well it worked.",
            "Careful. I have goals. You're cutting into the vision-board time.",
        ),
        "sprite": (
            "That's exactly the kind of thing I'd write in a song and never say out loud.",
            "Oh no, my whole face is doing a thing. The embarrassing swoon face.",
            "You can't just say things like that while the fountain does that romantic noise.",
        ),
        "tank": (
            "Ha! Smooth. I'm blushing and I don't blush. That's not true. I blush constantly.",
            "Okay, that's flirting. I know flirting. I watch a lot of romance movies at the gym.",
            "You're delightful. I don't know what else to do with this energy, so... flexes.",
        ),
        "trickster": (
            "Oh, we're flirting now? I should warn you, I flirt in riddles and pranks.",
            "Stop it. No, continue. This is my favorite genre of conversation.",
            "You're a menace. I like menaces. I am one.",
        ),
    },
    "ask_date": {
        "spark": (
            "A date? With me? Yes! Put it in the calendar before I schedule something dumber.",
            "Oh, that's lovely. I'm in. Let's do {venue}, or somewhere with snacks. Snacks preferred.",
            "Yes — but warn my group chat, they take bets on this stuff.",
        ),
        "storm": (
            "A date? Finally, a storyline with me as the lead. Yes. Obviously yes.",
            "I accept. But I'm a whole event, {player}. Dress accordingly. Bring opinions.",
            "Yes. And I'm telling everyone. Not to be dramatic. Okay, slightly to be dramatic.",
        ),
        "zen": (
            "Oh — yes. I'd like that. Somewhere quiet? With good tea, if possible.",
            "A date. That's a nice word for it. Yes, let's. I'll try not to overthink it. I'll fail.",
            "I'd really like that. Just — go slow with me? I mean that affectionately.",
        ),
        "gear": (
            "A date. Yes. Absolutely. I'll prepare conversational topics. That's a joke. Mostly.",
            "That sounds great. I should warn you, my restaurant small talk is 80% diagrams.",
            "Yes. I'd like that. Can we pick somewhere with decent lighting and no echo?",
        ),
        "flame": (
            "Yes. I'll admit my calendar is aggressive, but I'll make a slot. You're worth a slot.",
            "A date it is. I'll bring ambition and dessert opinions. Equal energy to both.",
            "Interested. Yes. Let's do something with a view and a plan. I love a plan.",
        ),
        "sprite": (
            "A date... wow. Okay. Yes. I'll absolutely write a song about it. Badly. Sweetly.",
            "That's the most romantic thing anyone's said to me this week, and the bar was a poem about a shoe.",
            "Yes. Somewhere that feels like a scene. Is that too much? I don't care, yes.",
        ),
        "tank": (
            "Yes! Are we eating? I hope we're eating. I'm eating either way, but I hope.",
            "A date with you? Absolutely. I'll be so normal about it. I'll fail beautifully.",
            "Yes. Let's do it. I'll bring the good energy and maybe a picnic. It's a whole thing.",
        ),
        "trickster": (
            "A date? For real? Okay. Yes. But no pranks. One prank. Maybe a small prank.",
            "Yes — but I have to warn you, I schedule romance around snacks.",
            "I'm in. I'm also sweating. That's romance, probably.",
        ),
    },
    "gossip": {
        "spark": (
            "Okay, so I heard the same thing, but from three sources and one was a dog. So, unconfirmed.",
            "Wait, that's actually news to me, and I'm never not informed. Hold on, let me sit.",
            "I'm not saying anything. Except that I've heard everything, and I have notes.",
        ),
        "storm": (
            "That's not even the half of it! There was a whole second act in the parking lot.",
            "I knew it. I felt it. I told no one and yet I knew it. That's intuition.",
            "Interesting. Continue. And I need names, dates, and lighting details.",
        ),
        "zen": (
            "Mm. I try not to trade in that. But it does sound like people are stressed.",
            "That feels like their business, honestly. But I hope they're okay.",
            "I heard something too. I'd rather not pass it along until I know it's true.",
        ),
        "gear": (
            "Unverified. Source? Because I've got two conflicting versions and one has better evidence.",
            "Gossip is just unpolished data. That said... say more.",
            "Careful. That's a claim with low confidence. It'll spread weirdly if nobody checks it.",
        ),
        "flame": (
            "I try to stay out of it, but I do note who says what. Leverage is leverage.",
            "Not my circus. But I'll say this — reputations are currencies, and people spend irresponsibly.",
            "Hm. That's a story someone wants told. Ask why.",
        ),
        "sprite": (
            "Oh, that's a whole novel. That's a title, a cover, and a sad acoustic version.",
            "I shouldn't. But also I'm an artist and this is material. So continue.",
            "That's terrible. Beautifully terrible. Like a song in a minor key.",
        ),
        "tank": (
            "I don't love that story. If it's not kind, let's not pass it on, yeah?",
            "I heard something similar, but I'm not repeating it. My mum would hear somehow. Mums do.",
            "Eh. Better to ask them directly. But I'll listen if you need to talk it out.",
        ),
        "trickster": (
            "Oh, the tea is piping. But who's serving it? That's the question. Nobody asks.",
            "I already knew. I caused 12% of it. Anyway, continue.",
            "Careful, that's a rumor — rumors are pranks without a punchline. Or with, sometimes.",
        ),
    },
    "invite": {
        "spark": (
            "I'm there. What should I bring? Because I'm bringing too much either way.",
            "Yes! {venue}, right? I'll be early and act like it's casual.",
            "In. Absolutely in. I'll update the group chat and we'll make it a thing.",
        ),
        "storm": (
            "I'll be there, and I'll make an entrance. It's the least I can do.",
            "Yes. And afterwards we'll discuss everything that happened in extreme detail.",
            "Count me in. I need somewhere to perform being normal. This'll do.",
        ),
        "zen": (
            "I'd like that. Somewhere calm? Or anywhere, really, if you're there.",
            "Yes, if the day allows. Thank you for thinking of me.",
            "I'll come. Thank you. It's nice to be invited places and not just asked for tea opinions.",
        ),
        "gear": (
            "Yes. Should I bring the good cable? I feel like I should bring the good cable.",
            "I'm in. Adding it to the calendar so my brain believes it's real.",
            "Sure! If it runs long, I'll need a snack window. I'm fragile about snacks.",
        ),
        "flame": (
            "Yes. Let's make it worth the time. I'm saying that warmly, I promise.",
            "I'm in. I may arrive late from work. I'll make it up to you with good conversation.",
            "Absolutely. And you know I'll ask for a recap of outcomes on the way home.",
        ),
        "sprite": (
            "Yes. I'll bring my camera. And maybe a song. A small song. A shy song.",
            "Oh, I'd like that. Is it bad that I'm already imagining the lighting?",
            "I'm in. I'll be the one in the corner, feeling things poetically.",
        ),
        "tank": (
            "I'm so there! Should I bring food? I'm bringing food. It's decided.",
            "Yes! And afterwards, snacks. With a plan like that, we can't lose.",
            "Absolutely in. I'll bring the energy and the sturdy folding chairs.",
        ),
        "trickster": (
            "I'm in. I'll behave. That's a lie but I'll try. 40% trying.",
            "Yes! Is it bad that my first thought is 'what's the prank potential'? Yes. I'm in anyway.",
            "I'm there. I'm bringing the chaos but in a controlled, beautifully wrapped way.",
        ),
    },
    "insult": {
        "spark": (
            "Whoa! Okay, that was sharp. I'm going to need a minute and a mango cake.",
            "Rude! I'm deleting one nice thing I said about you. One. The rest stand.",
            "Okay, that went straight to the hurt feelings folder. That folder is full, by the way.",
        ),
        "storm": (
            "Oh, we're doing this? Fine. But I want it on the record that you started the third act.",
            "That's a low blow. I'm dramatic, not bulletproof. Watch it.",
            "Careful. I can turn this into a public performance and neither of us wins.",
        ),
        "zen": (
            "That wasn't very kind. I'm going to step back for a bit.",
            "Okay. I don't fight like that. I'm going to go and get some air.",
            "That hurt. I'd rather talk properly when we're both calmer.",
        ),
        "gear": (
            "That was unnecessary. I'm going to log it and, honestly, feel bad about it.",
            "Hm. I'm not going to escalate that. But I am going to remember it.",
            "Okay. I don't know what I did, but I'm not going to argue in a public place.",
        ),
        "flame": (
            "That's uncalled for. I'm happy to have a real conversation, not a cheap shot.",
            "Don't. I don't do petty. I do decisive. There's a difference.",
            "That cost you something. I'm just not sure you realize how much yet.",
        ),
        "sprite": (
            "Oh. That one stung. I'm going to go write about it. Kindly. With a sad chord.",
            "That was mean. I thought we were having a nice moment.",
            "I don't really do fights. I'll be somewhere with better vibes. The fountain, probably.",
        ),
        "tank": (
            "Whoa, easy. That's not how we talk to people. Take a breath, okay?",
            "That was uncalled for. I'm going to walk it off. You should too.",
            "Not cool. I don't like this energy. Let's not do this here.",
        ),
        "trickster": (
            "Ooh, spicy. Careful though — that one landed. I'm allowed to have feelings and a whoopee cushion.",
            "Okay, that was too far. I'm going to be annoying in a much gentler way now.",
            "I'm choosing to hear 'you're devastatingly charming'. No, wait, that hurt. Give me a minute.",
        ),
    },
    "goodbye": {
        "spark": (
            "Go, go. I'll be here. I'm always here. It's a personality flaw.",
            "See you soon! I'll have new gossip and stale cake. Wait, that came out weird.",
            "Bye! Text me when you're home. Or later. I'm not the boss of you. I am a little.",
        ),
        "storm": (
            "Fine, leave me in the middle of my own monologue. I'll allow it.",
            "Goodbye, {player}. This has been a scene I'll describe at length later.",
            "Off you go. I'll stay here and be effortlessly mysterious.",
        ),
        "zen": (
            "Take care. Drink some water on the way.",
            "Bye for now. It was good to see you.",
            "Go gently. I'll be around.",
        ),
        "gear": (
            "Bye! I'll send you that article. You'll either love it or block me.",
            "See you. I'll finish my thought. It's a good thought. You're missing out.",
            "Okay, bye. Remember to back up your phone. That's all. Okay, bye.",
        ),
        "flame": (
            "Bye! Good talk. Let's do this again with a plan next time.",
            "See you. Finish strong, whatever that means for the rest of your day.",
            "Go be productive. Or restful. I support both, but I'm better at the first.",
        ),
        "sprite": (
            "Bye... this was nice. I'll put it in a song. Not a sad one. A hopeful one.",
            "See you around. Come find me by the fountain, I'm usually being artistic at it.",
            "Okay. Bye. Take the good vibe with you. I have plenty.",
        ),
        "tank": (
            "See you, buddy! Don't skip lunch. I mean it. I'll know.",
            "Later! Great chat. Going to go lift something heavy and think about it.",
            "Bye! I'll wave at you from across the park like a weirdo. It's a thing I do.",
        ),
        "trickster": (
            "Bye! Check your pockets. That's all I'll say. Check your pockets.",
            "Later, trouble. I'll be plotting. Lovingly. Mostly.",
            "Bye! If anyone asks, I was with you the whole time.",
        ),
    },
    "deep": {
        "spark": (
            "Okay, real talk: I fill my days with people so I don't have to hear my own thoughts too much.",
            "Sometimes I worry I'm everyone's favorite flavor and nobody's favorite meal. That was deep, right?",
            "You know what I'm scared of? Being forgotten. That's why I know everyone. It's armor, but it's warm.",
        ),
        "storm": (
            "I perform a lot. So nobody notices when the act gets heavy. Anyway, therapy is expensive.",
            "People think I'm loud. I'm actually just scared of silence. Keep that between us.",
            "My secret? I'd trade all the drama for one honest conversation. Don't quote me on it.",
        ),
        "zen": (
            "I think most people just want to be seen once without being asked to perform. That's it. That's the whole thing.",
            "I used to think peace was a place. Now I think it's a practice, like brushing your teeth.",
            "You know what my goal is? To be the person somebody can exhale around.",
        ),
        "gear": (
            "I solve problems so people need me. It's not a great strategy, but it's mine.",
            "The thing I'm most proud of has no metrics. I can't put it on a spreadsheet. That bothers me.",
            "Honestly? I'm loneliest in rooms where everyone's talking. Is that a bug or a feature?",
        ),
        "flame": (
            "The ambition is real. But sometimes I wonder if I'm building a life or a résumé.",
            "I don't know how to rest without feeling guilty. That's the honest version.",
            "I want to be respected. I'd settle for loved, but I'd like both. That's allowed, right?",
        ),
        "sprite": (
            "The songs are just me saying things I'm too scared to say to a face.",
            "I think art is a way to leave a trail so people can find you later.",
            "I'm afraid I'm all feelings and no foundation. Then someone hears a song and I'm fine again.",
        ),
        "tank": (
            "Big guy, big heart. Everyone forgets the second part. I lift, but I also worry.",
            "I like taking care of people. Sometimes I don't know who takes care of me. That's a thing I'm working on.",
            "My dad used to say: leave every room warmer. I'm trying. Some days the room fights back.",
        ),
        "trickster": (
            "I make people laugh so they don't see the rest. It's a great trick until it isn't.",
            "Underneath the chaos I'm mostly afraid of being boring. Wild, right?",
            "I once went three days without a prank. It was the loneliest three days of my life.",
        ),
    },
    "fallback": {
        "spark": (
            "Ooh, say more. I'm invested now and I don't want to be the only one.",
            "Okay, tell me everything. I have forty minutes and a snack.",
            "That's interesting. I have a theory. It's 60% based on eavesdropping.",
        ),
        "storm": (
            "Mmm. I need more details. Specifically the emotional ones.",
            "Say more. I'm composing the dramatized version in my head.",
            "Fascinating. Continue. I'm giving you my full attention for at least two minutes.",
        ),
        "zen": (
            "Mm. I'm listening. Take your time.",
            "That sounds like something worth sitting with.",
            "I hear you. Say what you need to say.",
        ),
        "gear": (
            "Interesting. Could you define that a bit more? I'm genuinely asking, not being annoying.",
            "Huh. I have three follow-up questions. Starting with 'really?'",
            "That's a thread worth pulling. Where did it start?",
        ),
        "flame": (
            "Okay, I'm listening. What's the goal, though? I like knowing the goal.",
            "Interesting. Let's get concrete. What actually happens next?",
            "Mhm. I'm interested. Is this a problem to solve or a feeling to feel?",
        ),
        "sprite": (
            "Mmm, that has a mood. If it were a color it'd be dusk.",
            "I'm listening. This is going in the notebook, if that's okay.",
            "Say more. I like the way you say things.",
        ),
        "tank": (
            "I'm following. Slowly, but I'm following. Say the last part again?",
            "Okay, I hear you. Do you want advice or do you want a snack? Both are available.",
            "Got it. That's a big thing. Let's take it one step at a time.",
        ),
        "trickster": (
            "Mysterious. I love it. Continue, but make it weirder.",
            "I'm listening. I'm also thinking about a prank, but I'm listening.",
            "That's a plot. I want a sequel. Tell me the sequel.",
        ),
    },
    "date_yes": {
        "spark": "Yes! I'm in. I'm already choosing an outfit. It's a whole production.",
        "storm": "Yes. And I want it to be a good story. Surprise me.",
        "zen": "Yes. Somewhere quiet would be lovely. I'll be there.",
        "gear": "Yes. I'll do my research on the menu. That's my idea of romance.",
        "flame": "Yes. Let's make it memorable. I'm bringing my best conversation.",
        "sprite": "Yes. I'll be nervous and poetic. It'll be charming, I hope.",
        "tank": "Yes! I'm so in. Should I bring snacks for the trip? I'm bringing snacks.",
        "trickster": "Yes. I'll be on my best behavior. Statistically someone's is.",
    },
    "date_no": {
        "spark": "Oh — that's really sweet of you. I'm not there yet, but I'd love to hang out as friends.",
        "storm": "I'm flattered, truly. But no — and I'd rather be honest than swirl you around for drama.",
        "zen": "That's kind. I don't feel that way, and I don't want to pretend. I hope we're okay.",
        "gear": "I'm going to say no, gently. I value our thing as it is, and I don't want to blur it.",
        "flame": "I'm honored. But no — I don't think we're aligned like that. I still respect you a lot.",
        "sprite": "Oh... I'm sorry. That's lovely, but my heart's not in that place right now. Can we still be friends?",
        "tank": "Aw, thank you. Genuinely. But I don't feel it like that. You're still my favorite person to talk to, though.",
        "trickster": "That's very sweet. I'm going to pass, though — and no prank, I promise. This one's sincere.",
    },
    "flirt_yes": {
        "spark": "Oh, you're going to make me blush. Keep going, I'm enjoying this.",
        "storm": "Careful, I respond to flirting with monologues. You've been warned.",
        "zen": "You're very sweet. I'm smiling. That's about as much as I can confirm right now.",
        "gear": "That... registered in a good way. I'm going to be weird about it for an hour.",
        "flame": "Okay, that was smooth. I'll allow a second attempt.",
        "sprite": "You're going to make me write a whole album, and I'll blame you.",
        "tank": "You're a charmer. I'm blushing — don't tell the gym.",
        "trickster": "You're trouble. I like trouble. This is going to be fun.",
    },
    "flirt_no": {
        "spark": "Oh — you're lovely, but I'm not reading it that way. Can we keep it friendly?",
        "storm": "Flattery accepted, but I'm not opening that door. Not with you. Sorry.",
        "zen": "That's kind, but I'd rather stay friends. I hope that's okay.",
        "gear": "I'm flattered, but no. I don't think of you like that.",
        "flame": "I'm going to redirect that compliment somewhere friendly. I hope that's clear.",
        "sprite": "You're sweet, but my heart's not there. I don't want to give you a sad song.",
        "tank": "Aw, buddy. Thank you, but I'm not feeling that. Let's not make it weird, yeah?",
        "trickster": "Charming! But no. And that's me being sincere, which is rare, so take it seriously.",
    },
    "gift_like": {
        "spark": "You got me {item}? You actually listened. I'm going to be emotional about this all week.",
        "storm": "For me? Oh, you understood the assignment. This is going on the shelf of honor.",
        "zen": "Oh — {item}. That's thoughtful. Thank you. Truly.",
        "gear": "Oh! {item}. That's exactly right. How did you know? Actually, don't tell me. Magic.",
        "flame": "That's a good gift. Specific. I notice specifics. Thank you.",
        "sprite": "This is the kind of thing I'd write a song about. Thank you. I love it.",
        "tank": "Ahh, {item}! You're a legend. I'm hugging you. Brace yourself.",
        "trickster": "A gift! For me? I'm suspicious and delighted. Mostly delighted.",
    },
    "gift_neutral": {
        "spark": "Aw, thank you! That's really sweet of you.",
        "storm": "For me? Thank you. I'll find a good spot for it.",
        "zen": "That's kind. Thank you, {player}.",
        "gear": "Thank you. That's thoughtful.",
        "flame": "Thank you. That's a nice gesture, and I appreciate it.",
        "sprite": "Thank you! That's lovely. I'll keep it somewhere special.",
        "tank": "Thank you! You didn't have to do that. I'm glad you did.",
        "trickster": "Ooh, a gift. You're getting good at this.",
    },
    "gift_dislike": {
        "spark": "Oh! That's... thoughtful. I'll find a home for it, promise.",
        "storm": "Hm. It's not quite my thing, but the gesture? The gesture is noted.",
        "zen": "Thank you. It's kind of you to think of me. It's not really me, but it's kind.",
        "gear": "Thank you. I'm not sure I have a use for it, honestly, but I appreciate the thought.",
        "flame": "That's a bold choice. Not mine, but bold. Thank you.",
        "sprite": "Oh! That's... a thing. Thank you. I'll keep it. Probably in a drawer. Lovingly.",
        "tank": "Aw, thanks. I'm not sure what to do with it, but it's the thought, right?",
        "trickster": "This is either a masterpiece or a prank. Either way, respect.",
    },
    "apology_yes": {
        "spark": "Okay. Apology accepted. But you're buying cake. That's the price of peace.",
        "storm": "Fine. You're forgiven. And I'm only slightly adding this to my origin story.",
        "zen": "Thank you for saying that. I accept. Let's move gently from here.",
        "gear": "Accepted. I appreciate the specifics. Let's reset.",
        "flame": "Accepted. Good. Now let's build something better out of this.",
        "sprite": "Thank you. I was more hurt than I let on. But yes, okay. We're good.",
        "tank": "We're good, buddy. I don't hold grudges. I hold protein shakes.",
        "trickster": "Apology accepted, with interest. You owe me one laugh.",
    },
    "apology_no": {
        "spark": "I hear you. I'm not there yet. Give me a little time, okay?",
        "storm": "That's a start. But a start isn't the finish line. Ask me again later.",
        "zen": "I appreciate the words. I need a little space before I say yes.",
        "gear": "I accept the words, but the trust part needs a re-run. Give it time.",
        "flame": "Noted. But I evaluate on actions, not just words. Show me.",
        "sprite": "Thank you for apologizing. I'm still a bit bruised. Let's try later.",
        "tank": "I appreciate that. I'm just not ready to pretend it didn't happen.",
        "trickster": "Hm. Words, words. I like actions. But I'm listening.",
    },
    "call_greeting": {
        "spark": "{player}! I saw your name and did a little dance. What's up?",
        "storm": "You called. How dramatic of you. I approve. Hello.",
        "zen": "Oh — hi. Hold on, let me turn the kettle off. Okay, hi.",
        "gear": "Hey! Good timing, I was staring at a wall thinking about a plan. Talk to me.",
        "flame": "Hello! You've caught me between two tasks. I'm happy about the interruption.",
        "sprite": "Hi... I was just playing something. It's going to be stuck in your head now.",
        "tank": "Hey buddy! Great timing. I just got back from the gym. I'm very hungry and very happy.",
        "trickster": "You called! I was literally about to call you. That's a lie. But it's a nice story.",
    },
    "call_bye": {
        "spark": "Okay, gotta go! This was lovely. Text me later. Or don't, I'll survive. Text me.",
        "storm": "Goodbye, darling. This call had excellent structure. I'll be telling people about it.",
        "zen": "Okay. Bye. Thanks for calling. That was a nice bit of my day.",
        "gear": "Alright, I'll let you go. I'll send you the link. Bye!",
        "flame": "Alright, back to work. Good call. Let's do it again.",
        "sprite": "Bye. This call is going in the memory box. A good one.",
        "tank": "Bye buddy! Stay hydrated. I mean it. I'll check.",
        "trickster": "Bye! Check your pockets. Still a bit funny. Okay, actually bye.",
    },
    "missed_call": {
        "spark": "Missed call from me! I was going to tell you something huge. Okay, medium. Call back.",
        "storm": "You missed my call. I had a monologue ready and everything.",
        "zen": "I called earlier — no rush. Just wanted to hear how your day went.",
        "gear": "Missed you — I had a thing to tell you, but it can wait. Call when you're free.",
        "flame": "Tried you earlier. No emergency. Just realized I hadn't heard your voice in a while.",
        "sprite": "I called. I wrote half a song while the phone rang. It's about waiting, of course.",
        "tank": "Hey! Tried calling. Nothing serious. I just found a new snack place and I need to talk about it.",
        "trickster": "You missed my call. This is now part of my ongoing investigation into you.",
    },
}

def line_pool(intent: str, archetype: str) -> tuple[str, ...]:
    """Return a tuple of lines for (intent, archetype), tolerating single strings."""
    pool = LINES.get(intent, {}).get(archetype, ())
    if isinstance(pool, str):
        return (pool,)
    return tuple(pool)


# Universal bridges used to stitch multi-intent replies together.
BRIDGES = {
    "soft": ["Also —", "And hey,", "By the way —", "Oh, and —"],
    "warm": ["Anyway,", "So,", "Here's a thought:", "Okay so,"],
    "sharp": ["Moving on.", "Anyway.", "Regardless —", "Right."],
}

# Perception hints used when an NPC notices the player's recent behavior.
MOOD_LINES = {
    "happy": ["You're glowing today, by the way.", "You look like today's treating you well.", "Good energy on you today — I noticed."],
    "sad": ["You look a little tired. Everything okay?", "Hey — rough day? I'm a good listener.", "You've got that 'long week' look. Talk to me."],
    "angry": ["You seem tense. Should I be worried, or should the street be worried?", "Who do I need to have a word with?", "I'm sensing some steam. Want to vent?"],
    "neutral": ["You seem steady today.", "Same calm energy as always.", "You've got a good listening face on."],
}

RUMOR_OPENERS = [
    "Word around {venue} is that {claim}.",
    "I heard this thirdhand, so grain of salt: {claim}.",
    "Someone swears they saw something that means {claim}. I'm unconvinced.",
    "Okay, but here's the thing — {claim}. Or so people keep saying.",
]

RUMOR_CHALLENGES = [
    "That's a big claim for something with no witnesses. Who told you?",
    "I've heard that too, but nobody can name the source. I'd be careful repeating it.",
    "Hmm. I don't believe that yet. Show me the evidence and I'll update.",
]

EVENT_CALLOUTS = {
    "chaos": [
        "{a} and {b} just set off a dust cloud by the {loc}. People are losing it.",
        "Full cartoon chaos at the {loc}: {a} versus {b}. Someone call a referee.",
        "There's a spinning dust cloud at the {loc}. {a} and {b} are inside it, allegedly.",
    ],
    "date": [
        "Saw {a} and {b} at the {loc}. Very cute. Very 'are they a thing?' energy.",
        "{a} and {b}, at the {loc}? The town is going to talk and I am the town.",
    ],
    "business": [
        "{a} is officially open for business. Neighborhood economics are changing.",
        "New business alert: {a}. Support local, or at least gossip locally.",
    ],
    "party": [
        "{a} is hosting a party at the {loc}. Bring snacks, leave drama.",
        "House party at {a}'s corner of {loc}! The good kind of chaos.",
    ],
    "rumor": [
        "Rumor has it {claim}. Nobody has receipts. Proceed accordingly.",
        "Heard a whisper: {claim}. Reminder: whispers are not witnesses.",
    ],
}

PERSONALITY_QUIRKS = {
    "spark": ["snorts when they laugh", "brings snacks everywhere", "remembers every birthday"],
    "storm": ["gestures with their whole body", "narrates their life softly", "always arrives with a story"],
    "zen": ["carries loose tea in their bag", "humming when they think no one's listening", "notices small changes"],
    "gear": ["takes notes in a tiny notebook", "quotes a documentary mid-sentence", "labels their spice jars"],
    "flame": ["checks their calendar during conversations", "has opinions about efficiency", "wears great shoes"],
    "sprite": ["hums in three keys", "collects ticket stubs", "photographs doorways"],
    "tank": ["high-fives strangers", "feeds neighborhood pigeons", "always has snacks"],
    "trickster": ["whistles their own theme song", "leaves doodles on receipts", "knows every shortcut"],
}


# ---------------------------------------------------------------------------
# Player-planted gossip. Deliberately small, social and non-defamatory: the
# comedy is in how a block reacts, not in what the claim says.
# ---------------------------------------------------------------------------
STIR_CLAIMS = [
    "{subject} has been quietly claiming they taught the cafe owner everything they know.",
    "{subject} keeps reheating the same story about the fountain and adding new characters.",
    "{subject} was seen measuring the square 'for a project' and won't say what project.",
    "{subject} has been telling people they invented the neighborhood's best sandwich.",
    "{subject} apparently has a spreadsheet ranking everyone's playlist taste.",
    "{subject} told at least two people they were the first to find the studio.",
    "{subject} has been returning books two chapters lighter and acting innocent.",
    "{subject} keeps leaving anonymous motivational notes on the notice board.",
]
