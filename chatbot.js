
const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');

form.addEventListener('submit', function(e) {
  e.preventDefault();
  const userText = input.value.trim();
  if (!userText) return;

  // Add user message
  const userMsg = document.createElement('div');
  userMsg.className = 'user-message';
  userMsg.textContent = userText;
  chatBox.appendChild(userMsg);

  // Add bot response (simple demo)
  const botMsg = document.createElement('div');
  botMsg.className = 'bot-message';
  botMsg.textContent = getBotResponse(userText);
  chatBox.appendChild(botMsg);

  input.value = '';
  chatBox.scrollTop = chatBox.scrollHeight;
});

function getBotResponse(message) {
  message = message.toLowerCase();
  if (message.includes('water')) return 'Your plant needs watering every 3 days. 💧';
  if (message.includes('light')) return 'Keep your plant near indirect sunlight. ☀️';
  if (message.includes('hello')) return 'Hey there! 🌿';
  return "I'm still learning! Ask me about watering or light ☀️💧";

}
