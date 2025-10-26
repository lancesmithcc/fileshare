(() => {
  const pickerRegistry = [];
  const registryMap = new Map();

  document.querySelectorAll('[data-emoji-picker-modal]').forEach((modal) => {
    const overlay = modal.querySelector('[data-emoji-picker-overlay]');
    const close = modal.querySelector('[data-emoji-picker-close]');
    const grid = modal.querySelector('[data-emoji-grid]');
    const search = modal.querySelector('[data-emoji-search-input]');
    if (!overlay || !close || !grid || !search) {
      return;
    }
    const registry = { modal, overlay, close, grid, search };
    pickerRegistry.push(registry);
    registryMap.set(modal, registry);
  });

  if (!pickerRegistry.length) {
    return;
  }

  let activePicker = null;
  let currentTextarea = null;

  // Comprehensive emoji collection with keywords for search
  const emojis = [
    // Smileys & Emotion
    { emoji: '😀', keywords: ['grinning', 'smile', 'happy'] },
    { emoji: '😃', keywords: ['smile', 'happy', 'joy'] },
    { emoji: '😄', keywords: ['smile', 'happy', 'joy', 'laugh'] },
    { emoji: '😁', keywords: ['grin', 'smile', 'happy'] },
    { emoji: '😆', keywords: ['laugh', 'satisfied', 'happy'] },
    { emoji: '😅', keywords: ['sweat', 'smile', 'relief'] },
    { emoji: '🤣', keywords: ['rofl', 'laugh', 'lol'] },
    { emoji: '😂', keywords: ['tears', 'laugh', 'joy', 'lol'] },
    { emoji: '🙂', keywords: ['smile', 'happy'] },
    { emoji: '🙃', keywords: ['upside', 'down', 'silly'] },
    { emoji: '😉', keywords: ['wink', 'flirt'] },
    { emoji: '😊', keywords: ['blush', 'smile', 'happy'] },
    { emoji: '😇', keywords: ['angel', 'halo', 'innocent'] },
    { emoji: '🥰', keywords: ['love', 'hearts', 'adore'] },
    { emoji: '😍', keywords: ['love', 'heart', 'eyes'] },
    { emoji: '🤩', keywords: ['star', 'eyes', 'excited'] },
    { emoji: '😘', keywords: ['kiss', 'love', 'heart'] },
    { emoji: '😗', keywords: ['kiss'] },
    { emoji: '😚', keywords: ['kiss', 'blush'] },
    { emoji: '😙', keywords: ['kiss', 'smile'] },
    { emoji: '🥲', keywords: ['tear', 'smile', 'grateful'] },
    { emoji: '😋', keywords: ['yum', 'delicious', 'tongue'] },
    { emoji: '😛', keywords: ['tongue', 'playful'] },
    { emoji: '😜', keywords: ['wink', 'tongue', 'crazy'] },
    { emoji: '🤪', keywords: ['crazy', 'wild', 'goofy'] },
    { emoji: '😝', keywords: ['tongue', 'squint', 'silly'] },
    { emoji: '🤑', keywords: ['money', 'rich', 'dollar'] },
    { emoji: '🤗', keywords: ['hug', 'embrace'] },
    { emoji: '🤭', keywords: ['giggle', 'oops', 'shy'] },
    { emoji: '🤫', keywords: ['shh', 'quiet', 'secret'] },
    { emoji: '🤔', keywords: ['thinking', 'hmm', 'consider'] },
    { emoji: '🤐', keywords: ['zipper', 'mouth', 'secret'] },
    { emoji: '🤨', keywords: ['eyebrow', 'suspicious', 'doubt'] },
    { emoji: '😐', keywords: ['neutral', 'meh'] },
    { emoji: '😑', keywords: ['expressionless', 'blank'] },
    { emoji: '😶', keywords: ['silence', 'blank', 'speechless'] },
    { emoji: '😏', keywords: ['smirk', 'sly'] },
    { emoji: '😒', keywords: ['unamused', 'side', 'eye'] },
    { emoji: '🙄', keywords: ['eye', 'roll', 'annoyed'] },
    { emoji: '😬', keywords: ['grimace', 'awkward', 'nervous'] },
    { emoji: '🤥', keywords: ['liar', 'pinocchio', 'lie'] },
    { emoji: '😌', keywords: ['relieved', 'calm', 'peaceful'] },
    { emoji: '😔', keywords: ['pensive', 'sad', 'down'] },
    { emoji: '😪', keywords: ['sleepy', 'tired', 'yawn'] },
    { emoji: '🤤', keywords: ['drool', 'hungry', 'sleep'] },
    { emoji: '😴', keywords: ['sleep', 'zzz', 'tired'] },
    { emoji: '😷', keywords: ['mask', 'sick', 'medical'] },
    { emoji: '🤒', keywords: ['thermometer', 'sick', 'ill'] },
    { emoji: '🤕', keywords: ['bandage', 'hurt', 'injured'] },
    { emoji: '🤢', keywords: ['nauseated', 'sick', 'gross'] },
    { emoji: '🤮', keywords: ['vomit', 'sick', 'puke'] },
    { emoji: '🤧', keywords: ['sneeze', 'sick', 'achoo'] },
    { emoji: '🥵', keywords: ['hot', 'heat', 'sweat'] },
    { emoji: '🥶', keywords: ['cold', 'freeze', 'freezing'] },
    { emoji: '😎', keywords: ['cool', 'sunglasses', 'awesome'] },
    { emoji: '🤓', keywords: ['nerd', 'geek', 'glasses'] },
    { emoji: '🧐', keywords: ['monocle', 'inspect', 'curious'] },
    { emoji: '😕', keywords: ['confused', 'puzzled'] },
    { emoji: '😟', keywords: ['worried', 'concerned'] },
    { emoji: '🙁', keywords: ['sad', 'frown'] },
    { emoji: '☹️', keywords: ['frown', 'sad', 'unhappy'] },
    { emoji: '😮', keywords: ['surprised', 'wow', 'shock'] },
    { emoji: '😯', keywords: ['hushed', 'surprised'] },
    { emoji: '😲', keywords: ['astonished', 'shock', 'amazed'] },
    { emoji: '😳', keywords: ['flushed', 'embarrassed', 'blush'] },
    { emoji: '🥺', keywords: ['pleading', 'puppy', 'eyes', 'please'] },
    { emoji: '😦', keywords: ['frown', 'mouth', 'open'] },
    { emoji: '😧', keywords: ['anguish', 'worried'] },
    { emoji: '😨', keywords: ['fearful', 'scared', 'afraid'] },
    { emoji: '😰', keywords: ['anxious', 'sweat', 'nervous'] },
    { emoji: '😥', keywords: ['sad', 'sweat', 'disappointed'] },
    { emoji: '😢', keywords: ['cry', 'tear', 'sad'] },
    { emoji: '😭', keywords: ['sob', 'cry', 'tears', 'bawl'] },
    { emoji: '😱', keywords: ['scream', 'fear', 'scared'] },
    { emoji: '😖', keywords: ['confounded', 'frustrated'] },
    { emoji: '😣', keywords: ['persevere', 'struggle'] },
    { emoji: '😞', keywords: ['disappointed', 'sad'] },
    { emoji: '😓', keywords: ['sweat', 'work', 'exercise'] },
    { emoji: '😩', keywords: ['weary', 'tired', 'exhausted'] },
    { emoji: '😫', keywords: ['tired', 'exhausted', 'fed', 'up'] },
    { emoji: '🥱', keywords: ['yawn', 'tired', 'bored'] },
    { emoji: '😤', keywords: ['triumph', 'smug', 'proud'] },
    { emoji: '😡', keywords: ['angry', 'mad', 'rage'] },
    { emoji: '😠', keywords: ['angry', 'mad', 'annoyed'] },
    { emoji: '🤬', keywords: ['curse', 'swear', 'symbols'] },
    { emoji: '😈', keywords: ['devil', 'evil', 'mischievous'] },
    { emoji: '👿', keywords: ['devil', 'angry', 'evil'] },
    { emoji: '💀', keywords: ['skull', 'dead', 'death'] },
    { emoji: '☠️', keywords: ['skull', 'crossbones', 'death'] },
    { emoji: '💩', keywords: ['poop', 'crap', 'shit'] },
    { emoji: '🤡', keywords: ['clown', 'joker'] },
    { emoji: '👹', keywords: ['ogre', 'monster'] },
    { emoji: '👺', keywords: ['goblin', 'monster'] },
    { emoji: '👻', keywords: ['ghost', 'boo', 'spooky'] },
    { emoji: '👽', keywords: ['alien', 'ufo', 'extraterrestrial'] },
    { emoji: '👾', keywords: ['alien', 'game', 'space', 'invader'] },
    { emoji: '🤖', keywords: ['robot', 'bot', 'ai'] },

    // Gestures & Body Parts
    { emoji: '👋', keywords: ['wave', 'hello', 'hi', 'bye'] },
    { emoji: '🤚', keywords: ['raised', 'back', 'hand', 'stop'] },
    { emoji: '🖐️', keywords: ['hand', 'fingers', 'palm'] },
    { emoji: '✋', keywords: ['hand', 'stop', 'wait'] },
    { emoji: '🖖', keywords: ['vulcan', 'spock', 'star', 'trek'] },
    { emoji: '👌', keywords: ['ok', 'okay', 'perfect'] },
    { emoji: '🤌', keywords: ['pinched', 'fingers', 'italian'] },
    { emoji: '🤏', keywords: ['pinch', 'small', 'tiny'] },
    { emoji: '✌️', keywords: ['peace', 'victory', 'two'] },
    { emoji: '🤞', keywords: ['fingers', 'crossed', 'luck', 'hope'] },
    { emoji: '🤟', keywords: ['love', 'you', 'rock', 'metal'] },
    { emoji: '🤘', keywords: ['rock', 'on', 'metal', 'horns'] },
    { emoji: '🤙', keywords: ['call', 'me', 'hang', 'loose', 'shaka'] },
    { emoji: '👈', keywords: ['point', 'left', 'finger'] },
    { emoji: '👉', keywords: ['point', 'right', 'finger'] },
    { emoji: '👆', keywords: ['point', 'up', 'finger'] },
    { emoji: '🖕', keywords: ['middle', 'finger', 'fuck', 'rude'] },
    { emoji: '👇', keywords: ['point', 'down', 'finger'] },
    { emoji: '☝️', keywords: ['point', 'up', 'index', 'one'] },
    { emoji: '👍', keywords: ['thumbs', 'up', 'yes', 'good', 'like'] },
    { emoji: '👎', keywords: ['thumbs', 'down', 'no', 'bad', 'dislike'] },
    { emoji: '✊', keywords: ['fist', 'punch', 'power'] },
    { emoji: '👊', keywords: ['fist', 'bump', 'punch'] },
    { emoji: '🤛', keywords: ['fist', 'left', 'bump'] },
    { emoji: '🤜', keywords: ['fist', 'right', 'bump'] },
    { emoji: '👏', keywords: ['clap', 'applause', 'bravo'] },
    { emoji: '🙌', keywords: ['hands', 'up', 'celebrate', 'praise'] },
    { emoji: '👐', keywords: ['open', 'hands', 'hug'] },
    { emoji: '🤲', keywords: ['palms', 'together', 'prayer', 'plead'] },
    { emoji: '🤝', keywords: ['handshake', 'deal', 'agreement'] },
    { emoji: '🙏', keywords: ['pray', 'thanks', 'please', 'namaste'] },

    // Hearts & Love
    { emoji: '💖', keywords: ['heart', 'sparkle', 'love'] },
    { emoji: '💗', keywords: ['heart', 'growing', 'love'] },
    { emoji: '💓', keywords: ['heart', 'beating', 'love'] },
    { emoji: '💞', keywords: ['hearts', 'revolving', 'love'] },
    { emoji: '💕', keywords: ['hearts', 'two', 'love'] },
    { emoji: '💟', keywords: ['heart', 'decoration', 'love'] },
    { emoji: '❣️', keywords: ['heart', 'exclamation', 'love'] },
    { emoji: '💔', keywords: ['broken', 'heart', 'sad', 'breakup'] },
    { emoji: '❤️', keywords: ['heart', 'love', 'red'] },
    { emoji: '🧡', keywords: ['heart', 'orange', 'love'] },
    { emoji: '💛', keywords: ['heart', 'yellow', 'love'] },
    { emoji: '💚', keywords: ['heart', 'green', 'love'] },
    { emoji: '💙', keywords: ['heart', 'blue', 'love'] },
    { emoji: '💜', keywords: ['heart', 'purple', 'love'] },
    { emoji: '🤎', keywords: ['heart', 'brown', 'love'] },
    { emoji: '🖤', keywords: ['heart', 'black', 'love'] },
    { emoji: '🤍', keywords: ['heart', 'white', 'love'] },
    { emoji: '💋', keywords: ['kiss', 'lips', 'love'] },
    { emoji: '💯', keywords: ['100', 'perfect', 'score', 'hundred'] },
    { emoji: '💢', keywords: ['anger', 'comic', 'mad'] },
    { emoji: '💥', keywords: ['boom', 'explosion', 'collision'] },
    { emoji: '💫', keywords: ['dizzy', 'star', 'sparkle'] },
    { emoji: '💦', keywords: ['sweat', 'water', 'drops'] },
    { emoji: '💨', keywords: ['dash', 'wind', 'fast'] },
    { emoji: '🕳️', keywords: ['hole', 'void'] },
    { emoji: '💬', keywords: ['speech', 'bubble', 'chat', 'message'] },
    { emoji: '👁️‍🗨️', keywords: ['eye', 'bubble', 'witness'] },
    { emoji: '🗨️', keywords: ['speech', 'bubble', 'left'] },
    { emoji: '🗯️', keywords: ['anger', 'bubble', 'mad'] },
    { emoji: '💭', keywords: ['thought', 'bubble', 'thinking'] },
    { emoji: '💤', keywords: ['zzz', 'sleep', 'tired'] },

    // Symbols
    { emoji: '✨', keywords: ['sparkles', 'shine', 'magic', 'stars'] },
    { emoji: '⭐', keywords: ['star', 'favorite'] },
    { emoji: '🌟', keywords: ['star', 'glowing', 'shine'] },
    { emoji: '💫', keywords: ['dizzy', 'star'] },
    { emoji: '✔️', keywords: ['check', 'yes', 'correct', 'done'] },
    { emoji: '✅', keywords: ['check', 'mark', 'yes', 'done', 'complete'] },
    { emoji: '❌', keywords: ['x', 'no', 'wrong', 'cancel', 'delete'] },
    { emoji: '❎', keywords: ['x', 'mark', 'no', 'cancel'] },
    { emoji: '➕', keywords: ['plus', 'add', 'more'] },
    { emoji: '➖', keywords: ['minus', 'subtract', 'less'] },
    { emoji: '➗', keywords: ['divide', 'division', 'math'] },
    { emoji: '✖️', keywords: ['multiply', 'times', 'x', 'math'] },
    { emoji: '🔥', keywords: ['fire', 'hot', 'lit', 'burn', 'flame'] },
    { emoji: '💧', keywords: ['drop', 'water', 'tear'] },
    { emoji: '🌊', keywords: ['wave', 'water', 'ocean', 'sea'] },
    { emoji: '⚡', keywords: ['lightning', 'bolt', 'electric', 'zap', 'energy'] },
    { emoji: '☀️', keywords: ['sun', 'sunny', 'bright', 'day'] },
    { emoji: '🌙', keywords: ['moon', 'night', 'crescent'] },
    { emoji: '⭐', keywords: ['star', 'favorite', 'best'] },
    { emoji: '🌈', keywords: ['rainbow', 'pride', 'colorful'] },
    { emoji: '☁️', keywords: ['cloud', 'weather'] },
    { emoji: '⛅', keywords: ['cloud', 'sun', 'partly', 'cloudy'] },
    { emoji: '🌤️', keywords: ['sun', 'cloud', 'mostly', 'sunny'] },
    { emoji: '⛈️', keywords: ['storm', 'rain', 'lightning'] },
    { emoji: '🌧️', keywords: ['rain', 'weather', 'cloud'] },
    { emoji: '⚡', keywords: ['lightning', 'thunder', 'bolt'] },
    { emoji: '❄️', keywords: ['snow', 'cold', 'winter'] },
    { emoji: '🔔', keywords: ['bell', 'notification', 'ring'] },
    { emoji: '🔕', keywords: ['bell', 'mute', 'silent'] },

    // Activities & Sports
    { emoji: '🎉', keywords: ['party', 'celebrate', 'confetti', 'celebration'] },
    { emoji: '🎊', keywords: ['confetti', 'ball', 'party', 'celebrate'] },
    { emoji: '🎈', keywords: ['balloon', 'party', 'celebrate'] },
    { emoji: '🎁', keywords: ['gift', 'present', 'birthday'] },
    { emoji: '🎂', keywords: ['cake', 'birthday', 'party'] },
    { emoji: '🎄', keywords: ['christmas', 'tree', 'holiday'] },
    { emoji: '🎃', keywords: ['halloween', 'pumpkin', 'jack-o-lantern'] },
    { emoji: '🏆', keywords: ['trophy', 'win', 'award', 'champion'] },
    { emoji: '🥇', keywords: ['first', 'gold', 'medal', 'winner'] },
    { emoji: '🥈', keywords: ['second', 'silver', 'medal'] },
    { emoji: '🥉', keywords: ['third', 'bronze', 'medal'] },
    { emoji: '⚽', keywords: ['soccer', 'ball', 'football', 'sport'] },
    { emoji: '🏀', keywords: ['basketball', 'ball', 'sport'] },
    { emoji: '🏈', keywords: ['football', 'ball', 'sport', 'american'] },
    { emoji: '⚾', keywords: ['baseball', 'ball', 'sport'] },
    { emoji: '🎾', keywords: ['tennis', 'ball', 'sport'] },
    { emoji: '🎮', keywords: ['game', 'controller', 'video', 'gaming'] },
    { emoji: '🎯', keywords: ['target', 'dart', 'bullseye', 'goal'] },
    { emoji: '🎲', keywords: ['dice', 'game', 'random'] },
    { emoji: '🎵', keywords: ['music', 'note', 'song'] },
    { emoji: '🎶', keywords: ['music', 'notes', 'song'] },
    { emoji: '🎤', keywords: ['microphone', 'sing', 'karaoke'] },
    { emoji: '🎧', keywords: ['headphones', 'music', 'audio'] },
    { emoji: '🎬', keywords: ['movie', 'film', 'cinema', 'clapper'] },
    { emoji: '🎨', keywords: ['art', 'paint', 'palette', 'creative'] },
    { emoji: '🎭', keywords: ['theater', 'drama', 'masks', 'performing'] },

    // Objects & Technology
    { emoji: '📱', keywords: ['phone', 'mobile', 'smartphone', 'cell'] },
    { emoji: '💻', keywords: ['computer', 'laptop', 'pc', 'mac'] },
    { emoji: '⌨️', keywords: ['keyboard', 'typing', 'computer'] },
    { emoji: '🖥️', keywords: ['computer', 'desktop', 'monitor'] },
    { emoji: '🖨️', keywords: ['printer', 'print', 'copy'] },
    { emoji: '🖱️', keywords: ['mouse', 'computer', 'click'] },
    { emoji: '💾', keywords: ['floppy', 'disk', 'save', 'storage'] },
    { emoji: '💿', keywords: ['cd', 'disc', 'optical'] },
    { emoji: '📀', keywords: ['dvd', 'disc', 'optical'] },
    { emoji: '📷', keywords: ['camera', 'photo', 'picture'] },
    { emoji: '📸', keywords: ['camera', 'flash', 'photo'] },
    { emoji: '🔋', keywords: ['battery', 'power', 'charge'] },
    { emoji: '🔌', keywords: ['plug', 'electric', 'power'] },
    { emoji: '💡', keywords: ['bulb', 'idea', 'light', 'think'] },
    { emoji: '🔦', keywords: ['flashlight', 'torch', 'light'] },
    { emoji: '🔍', keywords: ['search', 'magnify', 'find', 'zoom', 'look'] },
    { emoji: '🔎', keywords: ['search', 'magnify', 'find', 'zoom'] },
    { emoji: '🔐', keywords: ['lock', 'key', 'secure', 'locked'] },
    { emoji: '🔒', keywords: ['lock', 'secure', 'closed', 'private'] },
    { emoji: '🔓', keywords: ['unlock', 'open', 'unlocked'] },
    { emoji: '🔑', keywords: ['key', 'unlock', 'password'] },
    { emoji: '🗝️', keywords: ['old', 'key', 'antique'] },
    { emoji: '🚀', keywords: ['rocket', 'launch', 'space', 'ship', 'boost'] },
    { emoji: '🛸', keywords: ['ufo', 'alien', 'flying', 'saucer'] },
    { emoji: '✈️', keywords: ['airplane', 'plane', 'flight', 'travel'] },
    { emoji: '🚗', keywords: ['car', 'automobile', 'vehicle'] },
    { emoji: '🏠', keywords: ['house', 'home', 'building'] },
    { emoji: '🏡', keywords: ['house', 'garden', 'home'] },

    // Food & Drink
    { emoji: '🍕', keywords: ['pizza', 'food', 'italian'] },
    { emoji: '🍔', keywords: ['burger', 'hamburger', 'food'] },
    { emoji: '🍟', keywords: ['fries', 'french', 'food'] },
    { emoji: '🌭', keywords: ['hot', 'dog', 'food'] },
    { emoji: '🍿', keywords: ['popcorn', 'snack', 'movie'] },
    { emoji: '🥓', keywords: ['bacon', 'food', 'meat'] },
    { emoji: '🥚', keywords: ['egg', 'food'] },
    { emoji: '🍳', keywords: ['cooking', 'egg', 'frying', 'pan'] },
    { emoji: '🍞', keywords: ['bread', 'loaf', 'food'] },
    { emoji: '🥐', keywords: ['croissant', 'bread', 'pastry'] },
    { emoji: '🥖', keywords: ['baguette', 'bread', 'french'] },
    { emoji: '🥨', keywords: ['pretzel', 'snack'] },
    { emoji: '🥞', keywords: ['pancakes', 'breakfast', 'food'] },
    { emoji: '🧀', keywords: ['cheese', 'food'] },
    { emoji: '🍖', keywords: ['meat', 'bone', 'food'] },
    { emoji: '🍗', keywords: ['chicken', 'poultry', 'leg', 'food'] },
    { emoji: '🥩', keywords: ['steak', 'meat', 'food'] },
    { emoji: '🍤', keywords: ['shrimp', 'seafood', 'food'] },
    { emoji: '🍣', keywords: ['sushi', 'japanese', 'food'] },
    { emoji: '🍱', keywords: ['bento', 'box', 'japanese', 'food'] },
    { emoji: '🍜', keywords: ['ramen', 'noodles', 'bowl', 'food'] },
    { emoji: '🍝', keywords: ['spaghetti', 'pasta', 'italian', 'food'] },
    { emoji: '🍛', keywords: ['curry', 'rice', 'food'] },
    { emoji: '🍲', keywords: ['stew', 'pot', 'food'] },
    { emoji: '🥗', keywords: ['salad', 'green', 'healthy', 'food'] },
    { emoji: '🍦', keywords: ['ice', 'cream', 'dessert', 'sweet'] },
    { emoji: '🍧', keywords: ['shaved', 'ice', 'dessert'] },
    { emoji: '🍨', keywords: ['ice', 'cream', 'dessert'] },
    { emoji: '🍩', keywords: ['donut', 'doughnut', 'dessert', 'sweet'] },
    { emoji: '🍪', keywords: ['cookie', 'dessert', 'sweet'] },
    { emoji: '🎂', keywords: ['cake', 'birthday', 'dessert'] },
    { emoji: '🍰', keywords: ['cake', 'slice', 'dessert'] },
    { emoji: '🧁', keywords: ['cupcake', 'dessert', 'sweet'] },
    { emoji: '🍫', keywords: ['chocolate', 'bar', 'sweet'] },
    { emoji: '🍬', keywords: ['candy', 'sweet'] },
    { emoji: '🍭', keywords: ['lollipop', 'candy', 'sweet'] },
    { emoji: '🍮', keywords: ['custard', 'pudding', 'dessert'] },
    { emoji: '🍯', keywords: ['honey', 'pot', 'sweet'] },
    { emoji: '🍼', keywords: ['baby', 'bottle', 'milk'] },
    { emoji: '🥛', keywords: ['milk', 'glass', 'drink'] },
    { emoji: '☕', keywords: ['coffee', 'tea', 'hot', 'drink'] },
    { emoji: '🍵', keywords: ['tea', 'cup', 'drink'] },
    { emoji: '🍶', keywords: ['sake', 'bottle', 'drink'] },
    { emoji: '🍾', keywords: ['champagne', 'bottle', 'celebrate', 'drink'] },
    { emoji: '🍷', keywords: ['wine', 'glass', 'drink', 'alcohol'] },
    { emoji: '🍸', keywords: ['cocktail', 'martini', 'drink', 'alcohol'] },
    { emoji: '🍹', keywords: ['tropical', 'drink', 'cocktail'] },
    { emoji: '🍺', keywords: ['beer', 'mug', 'drink', 'alcohol'] },
    { emoji: '🍻', keywords: ['beers', 'cheers', 'drink', 'celebrate'] },
    { emoji: '🥂', keywords: ['champagne', 'glasses', 'cheers', 'celebrate'] },
    { emoji: '🥃', keywords: ['whiskey', 'tumbler', 'drink', 'alcohol'] },
    { emoji: '🥤', keywords: ['cup', 'straw', 'drink', 'soda'] },

    // Nature & Animals
    { emoji: '🐶', keywords: ['dog', 'puppy', 'pet', 'animal'] },
    { emoji: '🐱', keywords: ['cat', 'kitty', 'pet', 'animal'] },
    { emoji: '🐭', keywords: ['mouse', 'animal'] },
    { emoji: '🐹', keywords: ['hamster', 'pet', 'animal'] },
    { emoji: '🐰', keywords: ['rabbit', 'bunny', 'animal'] },
    { emoji: '🦊', keywords: ['fox', 'animal'] },
    { emoji: '🐻', keywords: ['bear', 'animal'] },
    { emoji: '🐼', keywords: ['panda', 'bear', 'animal'] },
    { emoji: '🐨', keywords: ['koala', 'animal'] },
    { emoji: '🐯', keywords: ['tiger', 'animal'] },
    { emoji: '🦁', keywords: ['lion', 'animal'] },
    { emoji: '🐮', keywords: ['cow', 'animal'] },
    { emoji: '🐷', keywords: ['pig', 'animal'] },
    { emoji: '🐸', keywords: ['frog', 'animal'] },
    { emoji: '🐵', keywords: ['monkey', 'animal'] },
    { emoji: '🐔', keywords: ['chicken', 'bird', 'animal'] },
    { emoji: '🐧', keywords: ['penguin', 'bird', 'animal'] },
    { emoji: '🐦', keywords: ['bird', 'animal'] },
    { emoji: '🦅', keywords: ['eagle', 'bird', 'animal'] },
    { emoji: '🦆', keywords: ['duck', 'bird', 'animal'] },
    { emoji: '🦢', keywords: ['swan', 'bird', 'animal'] },
    { emoji: '🦉', keywords: ['owl', 'bird', 'animal', 'wise'] },
    { emoji: '🦩', keywords: ['flamingo', 'bird', 'pink', 'animal'] },
    { emoji: '🦚', keywords: ['peacock', 'bird', 'animal'] },
    { emoji: '🐝', keywords: ['bee', 'honey', 'insect'] },
    { emoji: '🐛', keywords: ['bug', 'caterpillar', 'insect'] },
    { emoji: '🦋', keywords: ['butterfly', 'insect', 'pretty'] },
    { emoji: '🐌', keywords: ['snail', 'slow', 'shell'] },
    { emoji: '🐞', keywords: ['ladybug', 'insect', 'beetle'] },
    { emoji: '🐜', keywords: ['ant', 'insect'] },
    { emoji: '🕷️', keywords: ['spider', 'insect', 'web'] },
    { emoji: '🕸️', keywords: ['spider', 'web', 'halloween'] },
    { emoji: '🦂', keywords: ['scorpion', 'zodiac'] },
    { emoji: '🐍', keywords: ['snake', 'reptile'] },
    { emoji: '🦎', keywords: ['lizard', 'reptile'] },
    { emoji: '🐢', keywords: ['turtle', 'slow', 'reptile'] },
    { emoji: '🐠', keywords: ['fish', 'tropical'] },
    { emoji: '🐟', keywords: ['fish'] },
    { emoji: '🐡', keywords: ['blowfish', 'fish'] },
    { emoji: '🦈', keywords: ['shark', 'fish', 'dangerous'] },
    { emoji: '🐙', keywords: ['octopus', 'tentacles'] },
    { emoji: '🐚', keywords: ['shell', 'spiral', 'beach'] },
    { emoji: '🦀', keywords: ['crab', 'seafood'] },
    { emoji: '🦞', keywords: ['lobster', 'seafood'] },
    { emoji: '🦐', keywords: ['shrimp', 'seafood'] },
    { emoji: '🦑', keywords: ['squid', 'tentacles'] },
    { emoji: '🌸', keywords: ['flower', 'cherry', 'blossom', 'spring'] },
    { emoji: '🌺', keywords: ['flower', 'hibiscus', 'tropical'] },
    { emoji: '🌻', keywords: ['sunflower', 'flower'] },
    { emoji: '🌹', keywords: ['rose', 'flower', 'love'] },
    { emoji: '🌷', keywords: ['tulip', 'flower'] },
    { emoji: '🌼', keywords: ['blossom', 'flower'] },
    { emoji: '🌱', keywords: ['seedling', 'plant', 'grow'] },
    { emoji: '🌲', keywords: ['evergreen', 'tree', 'pine'] },
    { emoji: '🌳', keywords: ['tree', 'deciduous'] },
    { emoji: '🌴', keywords: ['palm', 'tree', 'tropical'] },
    { emoji: '🌵', keywords: ['cactus', 'desert', 'plant'] },
    { emoji: '🍀', keywords: ['clover', 'four', 'leaf', 'lucky', 'luck'] },
    { emoji: '🍁', keywords: ['maple', 'leaf', 'fall', 'canada'] },
    { emoji: '🍂', keywords: ['fallen', 'leaf', 'autumn', 'fall'] },
    { emoji: '🍃', keywords: ['leaves', 'wind', 'blow'] },

    // Money & Finance
    { emoji: '💰', keywords: ['money', 'bag', 'dollar', 'rich', 'cash'] },
    { emoji: '💸', keywords: ['money', 'wings', 'fly', 'spend'] },
    { emoji: '💵', keywords: ['dollar', 'bill', 'money', 'cash'] },
    { emoji: '💴', keywords: ['yen', 'money', 'japan'] },
    { emoji: '💶', keywords: ['euro', 'money', 'europe'] },
    { emoji: '💷', keywords: ['pound', 'money', 'uk', 'britain'] },
    { emoji: '💳', keywords: ['credit', 'card', 'payment', 'money'] },
    { emoji: '🪙', keywords: ['coin', 'money'] },
    { emoji: '💎', keywords: ['diamond', 'gem', 'jewel', 'precious'] },

    // Business & Office
    { emoji: '📈', keywords: ['chart', 'increase', 'up', 'trend', 'growth', 'stocks'] },
    { emoji: '📉', keywords: ['chart', 'decrease', 'down', 'trend', 'stocks'] },
    { emoji: '📊', keywords: ['chart', 'bar', 'data', 'stats'] },
    { emoji: '📅', keywords: ['calendar', 'date', 'schedule'] },
    { emoji: '📆', keywords: ['calendar', 'tear', 'off', 'date'] },
    { emoji: '📋', keywords: ['clipboard', 'list', 'tasks'] },
    { emoji: '📌', keywords: ['pin', 'pushpin', 'important'] },
    { emoji: '📍', keywords: ['pin', 'location', 'place', 'map'] },
    { emoji: '📎', keywords: ['paperclip', 'attach'] },
    { emoji: '📏', keywords: ['ruler', 'measure', 'straight'] },
    { emoji: '📐', keywords: ['triangle', 'ruler', 'set', 'square'] },
    { emoji: '✂️', keywords: ['scissors', 'cut', 'tool'] },
    { emoji: '🗂️', keywords: ['card', 'index', 'dividers', 'organize'] },
    { emoji: '📁', keywords: ['folder', 'file', 'directory'] },
    { emoji: '📂', keywords: ['folder', 'open', 'file'] },
    { emoji: '🗃️', keywords: ['card', 'file', 'box', 'storage'] },
    { emoji: '📝', keywords: ['memo', 'note', 'write', 'pencil'] },
    { emoji: '✏️', keywords: ['pencil', 'write', 'edit'] },
    { emoji: '✒️', keywords: ['pen', 'write', 'black'] },
    { emoji: '🖊️', keywords: ['pen', 'write'] },
    { emoji: '🖋️', keywords: ['pen', 'fountain', 'write'] },
    { emoji: '🖍️', keywords: ['crayon', 'draw', 'color'] },
    { emoji: '📚', keywords: ['books', 'library', 'read', 'study'] },
    { emoji: '📖', keywords: ['book', 'open', 'read'] },
    { emoji: '📕', keywords: ['book', 'closed', 'red'] },
    { emoji: '📗', keywords: ['book', 'green', 'closed'] },
    { emoji: '📘', keywords: ['book', 'blue', 'closed'] },
    { emoji: '📙', keywords: ['book', 'orange', 'closed'] },
    { emoji: '📓', keywords: ['notebook', 'write'] },
    { emoji: '📔', keywords: ['notebook', 'decorative', 'cover'] },
    { emoji: '📒', keywords: ['ledger', 'notebook'] },
    { emoji: '📃', keywords: ['page', 'curl', 'document'] },
    { emoji: '📜', keywords: ['scroll', 'paper', 'document'] },
    { emoji: '📄', keywords: ['page', 'document', 'paper'] },
    { emoji: '📰', keywords: ['newspaper', 'news', 'paper'] },
    { emoji: '🗞️', keywords: ['newspaper', 'rolled', 'news'] },
    { emoji: '📧', keywords: ['email', 'mail', 'letter', 'e-mail'] },
    { emoji: '✉️', keywords: ['envelope', 'mail', 'letter'] },
    { emoji: '📨', keywords: ['envelope', 'incoming', 'mail'] },
    { emoji: '📩', keywords: ['envelope', 'arrow', 'mail', 'send'] },
    { emoji: '📤', keywords: ['outbox', 'tray', 'mail', 'send'] },
    { emoji: '📥', keywords: ['inbox', 'tray', 'mail', 'receive'] },
    { emoji: '📦', keywords: ['package', 'box', 'parcel', 'delivery'] },
    { emoji: '📫', keywords: ['mailbox', 'mail', 'flag', 'up'] },
    { emoji: '📪', keywords: ['mailbox', 'mail', 'flag', 'down'] },

    // Time & Clock
    { emoji: '⏰', keywords: ['alarm', 'clock', 'time', 'wake'] },
    { emoji: '⏱️', keywords: ['stopwatch', 'timer', 'time'] },
    { emoji: '⏲️', keywords: ['timer', 'clock', 'time'] },
    { emoji: '⌚', keywords: ['watch', 'time', 'clock'] },
    { emoji: '🕐', keywords: ['one', 'oclock', 'time', 'clock'] },
    { emoji: '🕑', keywords: ['two', 'oclock', 'time', 'clock'] },
    { emoji: '🕒', keywords: ['three', 'oclock', 'time', 'clock'] },
    { emoji: '🕓', keywords: ['four', 'oclock', 'time', 'clock'] },
    { emoji: '🕔', keywords: ['five', 'oclock', 'time', 'clock'] },
    { emoji: '🕕', keywords: ['six', 'oclock', 'time', 'clock'] },
    { emoji: '🕖', keywords: ['seven', 'oclock', 'time', 'clock'] },
    { emoji: '🕗', keywords: ['eight', 'oclock', 'time', 'clock'] },
    { emoji: '🕘', keywords: ['nine', 'oclock', 'time', 'clock'] },
    { emoji: '🕙', keywords: ['ten', 'oclock', 'time', 'clock'] },
    { emoji: '🕚', keywords: ['eleven', 'oclock', 'time', 'clock'] },
    { emoji: '🕛', keywords: ['twelve', 'oclock', 'time', 'clock'] },
    { emoji: '⌛', keywords: ['hourglass', 'time', 'sand'] },
    { emoji: '⏳', keywords: ['hourglass', 'flowing', 'sand', 'time'] },
  ];

  let allEmojis = [...emojis]; // Keep a copy of all emojis

  function hidePicker(registry) {
    if (!registry) {
      return;
    }
    registry.modal.style.display = 'none';
    if (activePicker === registry) {
      activePicker = null;
      currentTextarea = null;
    }
  }

  function positionPicker(trigger, registry) {
    const chatWindow = trigger.closest('.chat-window');
    const tray = trigger.closest('[data-messenger-tray]');

    if (chatWindow && chatWindow.contains(registry.modal)) {
      registry.modal.classList.add('in-chat');
      registry.modal.classList.remove('in-popover');
    } else if (tray) {
      registry.modal.classList.add('in-popover');
      registry.modal.classList.remove('in-chat');
      if (registry.modal.parentElement !== tray) {
        tray.appendChild(registry.modal);
      }
    } else {
      registry.modal.classList.remove('in-chat');
      registry.modal.classList.remove('in-popover');
      if (registry.modal.parentElement !== document.body) {
        document.body.appendChild(registry.modal);
      }
    }
  }

  function resolvePickerForButton(button) {
    const chatWindow = button.closest('.chat-window');
    if (chatWindow) {
      const modal = chatWindow.querySelector('[data-emoji-picker-modal]');
      if (modal && registryMap.has(modal)) {
        return registryMap.get(modal);
      }
    }

    // Default to the first registered picker (global modal)
    return pickerRegistry[0];
  }

  function openPicker(registry, trigger) {
    if (!registry) {
      return;
    }

    if (activePicker && activePicker !== registry) {
      hidePicker(activePicker);
    }

    activePicker = registry;
    positionPicker(trigger, registry);
    registry.search.value = '';
    renderEmojis(allEmojis);
    registry.modal.style.display = 'block';
    registry.search.focus();
  }

  pickerRegistry.forEach((registry) => {
    registry.overlay.addEventListener('click', () => hidePicker(registry));
    registry.close.addEventListener('click', () => hidePicker(registry));
    registry.search.addEventListener('input', () => {
      if (activePicker !== registry) {
        return;
      }
      const query = registry.search.value.toLowerCase().trim();
      if (!query) {
        renderEmojis(allEmojis);
        return;
      }
      const filtered = allEmojis.filter((item) =>
        item.keywords.some((keyword) => keyword.includes(query))
      );
      renderEmojis(filtered);
    });
  });

  // Use event delegation for dynamically created buttons
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-emoji-picker-btn]');
    if (!btn) {
      return;
    }
    e.preventDefault();
    const form = btn.closest('form');
    currentTextarea = form ? form.querySelector('textarea') : null;
    const registry = resolvePickerForButton(btn);
    if (!registry) {
      return;
    }
    openPicker(registry, btn);
  });

  function renderEmojis(emojisToRender) {
    if (!activePicker) {
      return;
    }

    const grid = activePicker.grid;
    grid.innerHTML = '';

    if (emojisToRender.length === 0) {
      grid.innerHTML =
        '<p style="grid-column: 1 / -1; text-align: center; color: #888; padding: 2rem;">No emojis found</p>';
      return;
    }

    emojisToRender.forEach(item => {
      const emojiSpan = document.createElement('span');
      emojiSpan.textContent = item.emoji;
      emojiSpan.classList.add('emoji');
      emojiSpan.title = item.keywords.join(', '); // Show keywords on hover
      emojiSpan.addEventListener('click', () => {
        if (currentTextarea) {
          currentTextarea.value += item.emoji;
          currentTextarea.focus();
          hidePicker(activePicker);
        }
      });
      grid.appendChild(emojiSpan);
    });
  }
})();
