const express = require('express');
const { completeOrder, getDailyLog, getDailyLogHistory, resetDailyLog } = require('../controllers/dailyLogController');

const router = express.Router();

router.post('/orders/complete', completeOrder);
router.get('/daily-log', getDailyLog);
router.get('/daily-log/history', getDailyLogHistory);
router.post('/daily-log/reset', resetDailyLog);

module.exports = router;
