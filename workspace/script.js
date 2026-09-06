document.addEventListener('DOMContentLoaded', function() {
  // رسم الرسم البياني
  var ctx = document.getElementById('myChart').getContext('2d');
  var myChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['يناير', 'فبراير', 'مارس'],
      datasets: [{
        label: '# of Votes',
        data: [12, 19, 3],
        backgroundColor: [
          'rgba(255, 99, 132, 0.2)',
          'rgba(54, 162, 235, 0.2)',
          'rgba(255, 206, 86, 0.2)'
        ],
        borderColor: [
          'rgba(255, 99, 132, 1)',
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)'
        ],
        borderWidth: 1
      }]
    },
    options: {
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });

  // جعل الجدول متفاعلًا
  $(document).ready(function() {
    $('#example').DataTable();
  });

  // تبديل الوضع الداكن
  document.querySelector('body').classList.toggle('dark-mode');
});