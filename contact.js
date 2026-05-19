function collectContactInfo(event) {
  event.preventDefault();


  emailjs.sendForm('service_j9fm7l8', 'template_93hxh2u', '#contact-form')
    .then(function(response) {
      console.log('SUCCESS!', response.status, response.text);
      alert('Message sent successfully!');
      document.getElementById('contact-form').reset();
    }, function(error) {
      console.log('FAILED...', error);
      alert('Failed to send message. Please try again later.');
    });
}

document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('contact-form');
  if (form) {
    form.addEventListener('submit', collectContactInfo);
  }
});
  