(function () {
  'use strict';

  const tg = window.Telegram?.WebApp;

  // 1. Telegram Fullscreen Initialization
  if (tg) {
    tg.ready();
    if (typeof tg.disableVerticalSwipes === 'function') {
      tg.disableVerticalSwipes();
    }
    if (typeof tg.requestFullscreen === 'function') {
      tg.requestFullscreen();
    } else if (typeof tg.expand === 'function') {
      tg.expand();
    }
    if (tg.setHeaderColor && tg.themeParams?.secondary_bg_color) {
      tg.setHeaderColor(tg.themeParams.secondary_bg_color);
    }
  }

  const CURRENCY_SYMBOLS = {
    KZT: '₸',
    RUB: '₽',
    USD: '$',
    EUR: '€'
  };

  const SOURCE_LABELS = {
    text: 'текст',
    voice: 'голос',
    photo: 'чек',
    manual: 'вручную'
  };

  let userCurrency = 'KZT';
  let currencySymbol = '₸';
  let userInitialBalance = null;

  const userGreetingEl = document.getElementById('userGreeting');
  const currencyBadgeEl = document.getElementById('currencyBadge');
  const currentBalanceEl = document.getElementById('currentBalance');
  const totalExpenseEl = document.getElementById('totalExpense');
  const totalIncomeEl = document.getElementById('totalIncome');
  const txListEl = document.getElementById('txList');
  const loaderEl = document.getElementById('loader');
  const errorEl = document.getElementById('errorMessage');
  const emptyEl = document.getElementById('emptyMessage');
  const refreshBtn = document.getElementById('refreshBtn');

  function getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (tg && tg.initData) {
      headers['X-Telegram-Init-Data'] = tg.initData;
    }
    return headers;
  }

  function formatMoney(amount) {
    const num = Number(amount) || 0;
    const formatted = num.toLocaleString('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    return `${formatted} ${currencySymbol}`;
  }

  function formatDateGroup(isoDate) {
    const d = new Date(isoDate);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    if (d.toDateString() === today.toDateString()) return 'Сегодня';
    if (d.toDateString() === yesterday.toDateString()) return 'Вчера';

    return d.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: d.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
    });
  }

  function formatTime(isoDate) {
    return new Date(isoDate).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  async function fetchProfile() {
    try {
      const res = await fetch('/api/v1/auth/me', { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        userCurrency = data.currency || 'KZT';
        currencySymbol = CURRENCY_SYMBOLS[userCurrency] || userCurrency;
        userGreetingEl.textContent = data.first_name ? `Привет, ${data.first_name}!` : 'Smart Bujet';
        currencyBadgeEl.textContent = `${currencySymbol} ${userCurrency}`;
        if (data.initial_balance !== null && data.initial_balance !== undefined) {
          userInitialBalance = Number(data.initial_balance);
        }
        if (data.current_balance !== null && data.current_balance !== undefined) {
          currentBalanceEl.textContent = formatMoney(data.current_balance);
        }
      }
    } catch (e) {
      currencyBadgeEl.textContent = `${currencySymbol} ${userCurrency}`;
    }
  }

  async function fetchTransactions() {
    loaderEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
    emptyEl.classList.add('hidden');
    txListEl.innerHTML = '';

    try {
      const res = await fetch('/api/v1/transactions/?limit=100', { headers: getHeaders() });
      if (!res.ok) {
        if (res.status === 401) {
          throw new Error('Требуется авторизация через Telegram MiniApp.');
        }
        throw new Error(`Ошибка загрузки данных (${res.status})`);
      }
      const transactions = await res.json();
      renderTransactions(transactions);
    } catch (err) {
      errorEl.textContent = err.message || 'Не удалось загрузить транзакции';
      errorEl.classList.remove('hidden');
    } finally {
      loaderEl.classList.add('hidden');
    }
  }

  function renderTransactions(transactions) {
    if (!transactions || transactions.length === 0) {
      emptyEl.classList.remove('hidden');
      totalExpenseEl.textContent = formatMoney(0);
      totalIncomeEl.textContent = formatMoney(0);
      const balance = (userInitialBalance !== null ? userInitialBalance : 0);
      currentBalanceEl.textContent = formatMoney(balance);
      return;
    }

    let sumExpense = 0;
    let sumIncome = 0;
    const groups = {};

    transactions.forEach(tx => {
      const amt = Number(tx.amount) || 0;
      if (tx.type === 'income') {
        sumIncome += amt;
      } else {
        sumExpense += amt;
      }

      const groupKey = formatDateGroup(tx.transaction_date);
      if (!groups[groupKey]) {
        groups[groupKey] = [];
      }
      groups[groupKey].push(tx);
    });

    totalExpenseEl.textContent = formatMoney(sumExpense);
    totalIncomeEl.textContent = formatMoney(sumIncome);
    const balance = (userInitialBalance !== null ? userInitialBalance : 0) + sumIncome - sumExpense;
    currentBalanceEl.textContent = formatMoney(balance);

    const fragment = document.createDocumentFragment();

    Object.keys(groups).forEach(dateTitle => {
      const divider = document.createElement('div');
      divider.className = 'date-divider';
      divider.textContent = dateTitle;
      fragment.appendChild(divider);

      groups[dateTitle].forEach(tx => {
        const card = document.createElement('div');
        card.className = 'tx-card';

        const info = document.createElement('div');
        info.className = 'tx-info';

        const title = document.createElement('div');
        title.className = 'tx-title';
        title.textContent = tx.item_name || tx.category_name || 'Операция';

        const meta = document.createElement('div');
        meta.className = 'tx-meta';

        const categoryTag = document.createElement('span');
        categoryTag.className = 'tx-category';
        categoryTag.textContent = tx.category_name || 'Общее';

        const dot = document.createElement('span');
        dot.textContent = '•';

        const timeTag = document.createElement('span');
        timeTag.textContent = formatTime(tx.transaction_date);

        const sourceTag = document.createElement('span');
        sourceTag.className = 'tx-source-badge';
        sourceTag.textContent = SOURCE_LABELS[tx.source] || tx.source;

        meta.appendChild(categoryTag);
        meta.appendChild(dot);
        meta.appendChild(timeTag);
        meta.appendChild(sourceTag);

        info.appendChild(title);
        info.appendChild(meta);

        const amounts = document.createElement('div');
        amounts.className = 'tx-amounts';

        const finalAmount = document.createElement('div');
        const isIncome = tx.type === 'income';
        finalAmount.className = `tx-final-amount ${isIncome ? 'income' : 'expense'}`;
        finalAmount.textContent = `${isIncome ? '+' : '-'}${formatMoney(tx.amount)}`;
        amounts.appendChild(finalAmount);

        // Display discount if present
        if (tx.discount_amount && Number(tx.discount_amount) > 0) {
          const discountEl = document.createElement('div');
          discountEl.className = 'tx-discount';

          if (tx.original_amount) {
            const origEl = document.createElement('span');
            origEl.className = 'tx-original';
            origEl.textContent = formatMoney(tx.original_amount);
            discountEl.appendChild(origEl);
          }

          const saveEl = document.createElement('span');
          saveEl.textContent = `-${formatMoney(tx.discount_amount)}`;
          discountEl.appendChild(saveEl);

          amounts.appendChild(discountEl);
        }

        card.appendChild(info);
        card.appendChild(amounts);
        fragment.appendChild(card);
      });
    });

    txListEl.appendChild(fragment);
  }

  refreshBtn.addEventListener('click', () => {
    fetchProfile();
    fetchTransactions();
  });

  // Initial load
  fetchProfile().then(fetchTransactions);
})();
