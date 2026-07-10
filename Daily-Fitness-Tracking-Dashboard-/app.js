const path = require('path');
const express = require('express');
const apiRouter = require('./routes/api');
const { initDb } = require('./config/db');

const app = express();
app.use(express.json());
app.use('/api', apiRouter);
app.use(express.static(path.join(__dirname, 'public')));
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

if (require.main === module) {
  initDb().catch((error) => {
    console.error('Failed to initialize database:', error);
    process.exit(1);
  });

  const port = process.env.PORT || 3000;
  app.listen(port, () => {
    console.log(`NutriTrack dashboard running on http://localhost:${port}`);
  });
}

module.exports = app;
