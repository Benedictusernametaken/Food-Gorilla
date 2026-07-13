const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');
const app = express();
const PORT = 3000;

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());
app.use('/css', express.static(path.join(__dirname, 'public/css')));

app.use(require('./auth'));
app.use(require('./vendor_auth'));
app.use(require('./vendor_meals'));
app.use(require('./macro_calculator'));
app.use(require('./menu'));
app.use(require('./meal_builder'));

app.listen(PORT, () => {
    console.log(`Frontend UI server running on http://localhost:${PORT}`);
});