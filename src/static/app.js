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

  const ASSET_TYPE_LABELS = {
    deposit: 'Вклад',
    currency: 'Валюта',
    savings: 'Копилка',
    investment: 'Инвестиции'
  };

  let userCurrency = 'KZT';
  let currencySymbol = '₸';
  let userLiquidBalance = 0;

  // DOM Elements - Navigation & Topbar
  const userGreetingEl = document.getElementById('userGreeting');
  const currencyBadgeEl = document.getElementById('currencyBadge');
  const navOpsBtn = document.getElementById('navOpsBtn');
  const navAssetsBtn = document.getElementById('navAssetsBtn');
  const navFamilyBtn = document.getElementById('navFamilyBtn');
  const tabOps = document.getElementById('tab-operations');
  const tabAssets = document.getElementById('tab-assets');
  const tabFamily = document.getElementById('tab-family');

  // DOM Elements - Family Tab
  const familyLoaderEl = document.getElementById('familyLoader');
  const familyErrorMessageEl = document.getElementById('familyErrorMessage');
  const familyErrorTextEl = document.getElementById('familyErrorText');
  const retryFamilyBtn = document.getElementById('retryFamilyBtn');
  const familyWaitingStateEl = document.getElementById('familyWaitingState');
  const familyActiveStateEl = document.getElementById('familyActiveState');
  const familyInviteInput = document.getElementById('familyInviteInput');
  const copyInviteBtn = document.getElementById('copyInviteBtn');
  const shareInviteBtn = document.getElementById('shareInviteBtn');
  const copyToastEl = document.getElementById('copyToast');
  const familyGroupNameEl = document.getElementById('familyGroupName');
  const familyCombinedBalanceEl = document.getElementById('familyCombinedBalance');
  const familyTotalExpenseEl = document.getElementById('familyTotalExpense');
  const familyTotalIncomeEl = document.getElementById('familyTotalIncome');
  const familyMembersGridEl = document.getElementById('familyMembersGrid');
  const familyTxListEl = document.getElementById('familyTxList');
  const refreshFamilyBtn = document.getElementById('refreshFamilyBtn');
  const leaveFamilyBtn = document.getElementById('leaveFamilyBtn');

  // DOM Elements - Operations Tab
  const currentBalanceEl = document.getElementById('currentBalance');
  const totalExpenseEl = document.getElementById('totalExpense');
  const totalIncomeEl = document.getElementById('totalIncome');
  const expensePeriodLabelEl = document.getElementById('expensePeriodLabel');
  const incomePeriodLabelEl = document.getElementById('incomePeriodLabel');
  const txListEl = document.getElementById('txList');
  const loaderEl = document.getElementById('loader');
  const errorEl = document.getElementById('errorMessage');
  const emptyEl = document.getElementById('emptyMessage');
  const refreshBtn = document.getElementById('refreshBtn');

  // DOM Elements - Assets Tab
  const totalNetWorthEl = document.getElementById('totalNetWorth');
  const liquidWorthEl = document.getElementById('liquidWorth');
  const lockedWorthEl = document.getElementById('lockedWorth');
  const assetsListEl = document.getElementById('assetsList');
  const assetsLoaderEl = document.getElementById('assetsLoader');
  const assetsEmptyEl = document.getElementById('assetsEmpty');
  const addAssetBtn = document.getElementById('addAssetBtn');

  // DOM Elements - Modals
  const addAssetModal = document.getElementById('addAssetModal');
  const closeAddModalBtn = document.getElementById('closeAddModalBtn');
  const addAssetForm = document.getElementById('addAssetForm');
  const actionModal = document.getElementById('actionModal');
  const closeActionModalBtn = document.getElementById('closeActionModalBtn');
  const actionForm = document.getElementById('actionForm');
  const actionModalTitle = document.getElementById('actionModalTitle');
  const actionModalDesc = document.getElementById('actionModalDesc');
  const actionAssetIdInput = document.getElementById('actionAssetId');
  const actionTypeInput = document.getElementById('actionType');
  const actionAmountInput = document.getElementById('actionAmountInput');

  function getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (tg && tg.initData) {
      headers['X-Telegram-Init-Data'] = tg.initData;
    }
    return headers;
  }

  function formatMoney(amount, curr = null) {
    const num = Number(amount) || 0;
    const sym = curr ? (CURRENCY_SYMBOLS[curr] || curr) : currencySymbol;
    const formatted = num.toLocaleString('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    return `${formatted} ${sym}`;
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

  // --- Tab Navigation ---
  function switchTab(tabId) {
    [tabOps, tabAssets, tabFamily].forEach(t => t && t.classList.remove('active'));
    [navOpsBtn, navAssetsBtn, navFamilyBtn].forEach(b => b && b.classList.remove('active'));

    if (tabId === 'tab-family') {
      if (tabFamily) tabFamily.classList.add('active');
      if (navFamilyBtn) navFamilyBtn.classList.add('active');
      fetchFamilySummary();
    } else if (tabId === 'tab-assets') {
      if (tabAssets) tabAssets.classList.add('active');
      if (navAssetsBtn) navAssetsBtn.classList.add('active');
      fetchAssets();
    } else {
      if (tabOps) tabOps.classList.add('active');
      if (navOpsBtn) navOpsBtn.classList.add('active');
    }
  }

  if (navOpsBtn) navOpsBtn.addEventListener('click', () => switchTab('tab-operations'));
  if (navAssetsBtn) navAssetsBtn.addEventListener('click', () => switchTab('tab-assets'));
  if (navFamilyBtn) navFamilyBtn.addEventListener('click', () => switchTab('tab-family'));

  // --- Data Fetching ---
  async function fetchProfile() {
    try {
      const res = await fetch('/api/v1/auth/me', { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        userCurrency = data.currency || 'KZT';
        currencySymbol = CURRENCY_SYMBOLS[userCurrency] || userCurrency;
        userGreetingEl.textContent = data.first_name ? `Привет, ${data.first_name}!` : 'Smart Bujet';
        currencyBadgeEl.textContent = `${currencySymbol} ${userCurrency}`;

        userLiquidBalance = Number(data.current_balance || 0);
        currentBalanceEl.textContent = formatMoney(userLiquidBalance);

        // Calendar Month bound values directly from DB
        totalExpenseEl.textContent = formatMoney(data.month_expense || 0);
        totalIncomeEl.textContent = formatMoney(data.month_income || 0);

        if (data.month_period_name) {
          expensePeriodLabelEl.textContent = `Расход (${data.month_period_name.toLowerCase()})`;
          incomePeriodLabelEl.textContent = `Доход (${data.month_period_name.toLowerCase()})`;
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
      return;
    }

    const groups = {};
    transactions.forEach(tx => {
      const groupKey = formatDateGroup(tx.transaction_date);
      if (!groups[groupKey]) {
        groups[groupKey] = [];
      }
      groups[groupKey].push(tx);
    });

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

        meta.appendChild(categoryTag);
        meta.appendChild(dot);
        meta.appendChild(timeTag);

        info.appendChild(title);
        info.appendChild(meta);

        const amounts = document.createElement('div');
        amounts.className = 'tx-amounts';

        const finalAmount = document.createElement('div');
        let prefix = '-';
        let amountClass = 'expense';

        if (tx.type === 'income') {
          prefix = '+';
          amountClass = 'income';
        } else if (tx.type === 'transfer_out') {
          prefix = '→ ';
          amountClass = 'transfer';
        } else if (tx.type === 'transfer_in') {
          prefix = '← ';
          amountClass = 'transfer';
        }

        finalAmount.className = `tx-final-amount ${amountClass}`;
        finalAmount.textContent = `${prefix}${formatMoney(tx.amount)}`;
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

  // --- Assets & Deposits Management ---
  async function fetchAssets() {
    assetsLoaderEl.classList.remove('hidden');
    assetsEmptyEl.classList.add('hidden');
    assetsListEl.innerHTML = '';

    try {
      const res = await fetch('/api/v1/assets/summary', { headers: getHeaders() });
      if (!res.ok) {
        throw new Error('Ошибка загрузки активов');
      }
      const data = await res.json();
      renderAssets(data);
    } catch (err) {
      console.error(err);
    } finally {
      assetsLoaderEl.classList.add('hidden');
    }
  }

  function renderAssets(summary) {
    const totalAssets = Number(summary.total_assets || 0);
    const netWorth = userLiquidBalance + totalAssets;

    totalNetWorthEl.textContent = formatMoney(netWorth, summary.base_currency);
    liquidWorthEl.textContent = formatMoney(userLiquidBalance, summary.base_currency);
    lockedWorthEl.textContent = formatMoney(totalAssets, summary.base_currency);

    const accounts = summary.accounts || [];
    if (accounts.length === 0) {
      assetsEmptyEl.classList.remove('hidden');
      return;
    }

    const fragment = document.createDocumentFragment();

    accounts.forEach(acc => {
      const card = document.createElement('div');
      card.className = 'asset-card';

      const main = document.createElement('div');
      main.className = 'asset-main';

      const title = document.createElement('div');
      title.className = 'asset-title';
      title.textContent = acc.name;

      const meta = document.createElement('div');
      meta.className = 'asset-meta';

      const typeBadge = document.createElement('span');
      typeBadge.className = 'asset-type-badge';
      typeBadge.textContent = ASSET_TYPE_LABELS[acc.type] || acc.type;
      meta.appendChild(typeBadge);

      if (acc.interest_rate) {
        const rateBadge = document.createElement('span');
        rateBadge.className = 'asset-rate-badge';
        rateBadge.textContent = `${acc.interest_rate}% год.`;
        meta.appendChild(rateBadge);
      }

      main.appendChild(title);
      main.appendChild(meta);

      const side = document.createElement('div');
      side.className = 'asset-side';

      const balanceEl = document.createElement('div');
      balanceEl.className = 'asset-balance';
      balanceEl.textContent = formatMoney(acc.balance, acc.currency);
      side.appendChild(balanceEl);

      if (acc.currency !== summary.base_currency && acc.converted_balance) {
        const convEl = document.createElement('div');
        convEl.className = 'asset-converted';
        convEl.textContent = `≈ ${formatMoney(acc.converted_balance, summary.base_currency)}`;
        side.appendChild(convEl);
      }

      const btnGroup = document.createElement('div');
      btnGroup.className = 'asset-btn-group';

      const depBtn = document.createElement('button');
      depBtn.className = 'btn-mini deposit';
      depBtn.textContent = '+ Пополнить';
      depBtn.addEventListener('click', () => openActionModal(acc, 'deposit'));

      const wthBtn = document.createElement('button');
      wthBtn.className = 'btn-mini withdraw';
      wthBtn.textContent = '− Снять';
      wthBtn.addEventListener('click', () => openActionModal(acc, 'withdraw'));

      btnGroup.appendChild(depBtn);
      btnGroup.appendChild(wthBtn);
      side.appendChild(btnGroup);

      card.appendChild(main);
      card.appendChild(side);
      fragment.appendChild(card);
    });

    assetsListEl.appendChild(fragment);
  }

  // --- Modals Logic ---
  const addAssetErrorEl = document.getElementById('addAssetError');
  const addAssetSubmitBtn = document.getElementById('addAssetSubmitBtn');
  const actionModalErrorEl = document.getElementById('actionModalError');
  const actionSubmitBtn = document.getElementById('actionSubmitBtn');

  addAssetBtn.addEventListener('click', () => {
    if (addAssetErrorEl) addAssetErrorEl.classList.add('hidden');
    addAssetModal.classList.remove('hidden');
  });

  closeAddModalBtn.addEventListener('click', () => {
    addAssetModal.classList.add('hidden');
  });

  addAssetForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('assetNameInput').value.trim();
    const type = document.getElementById('assetTypeSelect').value;
    const currency = document.getElementById('assetCurrencySelect').value;
    const initial_balance = Number(document.getElementById('assetBalanceInput').value) || 0;
    const rateVal = document.getElementById('assetRateInput').value;
    const interest_rate = rateVal ? Number(rateVal) : null;

    if (addAssetErrorEl) addAssetErrorEl.classList.add('hidden');
    if (addAssetSubmitBtn) {
      addAssetSubmitBtn.disabled = true;
      addAssetSubmitBtn.textContent = 'Создание...';
    }

    try {
      const res = await fetch('/api/v1/assets/', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ name, type, currency, initial_balance, interest_rate })
      });
      if (res.ok) {
        addAssetModal.classList.add('hidden');
        addAssetForm.reset();
        await fetchProfile();
        await fetchAssets();
      } else {
        const err = await res.json().catch(() => ({}));
        const errMsg = err.detail || 'Не удалось создать счёт';
        if (addAssetErrorEl) {
          addAssetErrorEl.textContent = errMsg;
          addAssetErrorEl.classList.remove('hidden');
        } else {
          alert(errMsg);
        }
      }
    } catch (err) {
      if (addAssetErrorEl) {
        addAssetErrorEl.textContent = 'Ошибка при создании счёта: ' + (err.message || '');
        addAssetErrorEl.classList.remove('hidden');
      } else {
        alert('Ошибка при создании счёта');
      }
    } finally {
      if (addAssetSubmitBtn) {
        addAssetSubmitBtn.disabled = false;
        addAssetSubmitBtn.textContent = 'Создать счёт';
      }
    }
  });

  function openActionModal(account, type) {
    actionAssetIdInput.value = account.id;
    actionTypeInput.value = type;
    actionAmountInput.value = '';
    if (actionModalErrorEl) actionModalErrorEl.classList.add('hidden');

    if (type === 'deposit') {
      actionModalTitle.textContent = `Пополнить: ${account.name}`;
      actionModalDesc.textContent = `Средства спишутся со свободного баланса в актив (${account.currency})`;
    } else {
      actionModalTitle.textContent = `Снять: ${account.name}`;
      actionModalDesc.textContent = `Средства вернутся из актива на свободный баланс`;
    }
    actionModal.classList.remove('hidden');
    actionAmountInput.focus();
  }

  closeActionModalBtn.addEventListener('click', () => {
    actionModal.classList.add('hidden');
  });

  actionForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const assetId = actionAssetIdInput.value;
    const actionType = actionTypeInput.value;
    const amount = Number(actionAmountInput.value);

    if (actionModalErrorEl) actionModalErrorEl.classList.add('hidden');

    if (!amount || amount <= 0) {
      if (actionModalErrorEl) {
        actionModalErrorEl.textContent = 'Укажите корректную сумму';
        actionModalErrorEl.classList.remove('hidden');
      } else {
        alert('Укажите корректную сумму');
      }
      return;
    }

    if (actionSubmitBtn) {
      actionSubmitBtn.disabled = true;
      actionSubmitBtn.textContent = 'Обработка...';
    }

    try {
      const res = await fetch(`/api/v1/assets/${assetId}/${actionType}`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ amount })
      });
      if (res.ok) {
        actionModal.classList.add('hidden');
        actionForm.reset();
        await fetchProfile();
        await fetchAssets();
        await fetchTransactions();
      } else {
        const err = await res.json().catch(() => ({}));
        const errMsg = err.detail || 'Ошибка выполнения операции';
        if (actionModalErrorEl) {
          actionModalErrorEl.textContent = errMsg;
          actionModalErrorEl.classList.remove('hidden');
        } else {
          alert(errMsg);
        }
      }
    } catch (err) {
      if (actionModalErrorEl) {
        actionModalErrorEl.textContent = 'Ошибка соединения с сервером';
        actionModalErrorEl.classList.remove('hidden');
      } else {
        alert('Ошибка соединения с сервером');
      }
    } finally {
      if (actionSubmitBtn) {
        actionSubmitBtn.disabled = false;
        actionSubmitBtn.textContent = 'Подтвердить';
      }
    }
  });

  // --- Family Budget Logic ---
  async function fetchFamilySummary() {
    if (!familyLoaderEl) return;
    if (familyErrorMessageEl) familyErrorMessageEl.classList.add('hidden');
    familyLoaderEl.classList.remove('hidden');
    if (familyWaitingStateEl) familyWaitingStateEl.classList.add('hidden');
    if (familyActiveStateEl) familyActiveStateEl.classList.add('hidden');

    try {
      const res = await fetch('/api/v1/family/summary', { headers: getHeaders() });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Ошибка сервера (${res.status})`);
      }
      const data = await res.json();

      if (data.status === 'single_member') {
        // State 1: Single member (invite link visible)
        if (familyInviteInput) familyInviteInput.value = data.invite_link || '';
        if (familyWaitingStateEl) familyWaitingStateEl.classList.remove('hidden');
      } else {
        // State 2: Active family (invite link hidden)
        if (familyGroupNameEl) familyGroupNameEl.textContent = data.name || 'Семейный бюджет';
        if (familyCombinedBalanceEl) familyCombinedBalanceEl.textContent = formatMoney(data.combined_balance, data.currency);
        if (familyTotalExpenseEl) familyTotalExpenseEl.textContent = formatMoney(data.combined_month_expense, data.currency);
        if (familyTotalIncomeEl) familyTotalIncomeEl.textContent = formatMoney(data.combined_month_income, data.currency);

        renderFamilyMembers(data.members, data.currency);
        await fetchFamilyTransactions();
        if (familyActiveStateEl) familyActiveStateEl.classList.remove('hidden');
      }
    } catch (err) {
      console.error('Family summary error:', err);
      if (familyErrorMessageEl) {
        if (familyErrorTextEl) {
          familyErrorTextEl.textContent = err.message || 'Не удалось загрузить семейный профиль';
        }
        familyErrorMessageEl.classList.remove('hidden');
      }
    } finally {
      if (familyLoaderEl) familyLoaderEl.classList.add('hidden');
    }
  }

  function renderFamilyMembers(members, defaultCurr) {
    if (!familyMembersGridEl) return;
    familyMembersGridEl.innerHTML = '';
    (members || []).forEach(m => {
      const card = document.createElement('div');
      card.className = `member-card ${m.is_current_user ? 'self' : 'partner'}`;
      card.innerHTML = `
        <div class="member-header">
          <span class="member-name">${m.first_name || 'Участник'}</span>
          <span class="member-badge">${m.is_current_user ? 'Вы' : 'Партнёр'}</span>
        </div>
        <div class="member-balance">${formatMoney(m.current_balance, m.currency || defaultCurr)}</div>
        <div class="member-stats">
          <span>Расход: <b>${formatMoney(m.month_expense, m.currency || defaultCurr)}</b></span>
        </div>
      `;
      familyMembersGridEl.appendChild(card);
    });
  }

  async function fetchFamilyTransactions() {
    if (!familyTxListEl) return;
    try {
      const res = await fetch('/api/v1/family/transactions?limit=60', { headers: getHeaders() });
      if (!res.ok) return;
      const txs = await res.json();
      renderFamilyTransactions(txs);
    } catch (e) {
      console.error('Family transactions error:', e);
    }
  }

  function renderFamilyTransactions(transactions) {
    if (!familyTxListEl) return;
    familyTxListEl.innerHTML = '';
    if (!transactions || !transactions.length) {
      familyTxListEl.innerHTML = `
        <div class="empty-banner" style="padding: 30px 20px;">
          <div class="empty-icon">🧾</div>
          <p class="empty-title">Семейных транзакций пока нет</p>
          <span class="empty-desc">Любая трата или доход партнеров появится здесь автоматически</span>
        </div>
      `;
      return;
    }

    transactions.forEach(tx => {
      const el = document.createElement('div');
      el.className = 'tx-item';
      const isInc = tx.type === 'income';
      const authorClass = tx.is_current_user ? 'author-self' : 'author-partner';

      el.innerHTML = `
        <div class="tx-main">
          <div class="tx-top-row">
            <span class="tx-title">${tx.item_name || tx.category_name || 'Операция'}</span>
            <span class="author-tag ${authorClass}">${tx.author_name}</span>
          </div>
          <div class="tx-sub-row">
            <span class="tx-date">${formatDateGroup(tx.transaction_date)} • ${formatTime(tx.transaction_date)}</span>
            <span class="tx-cat-chip">${tx.category_name || ''}</span>
          </div>
        </div>
        <div class="tx-amount ${isInc ? 'income' : 'expense'}">
          ${isInc ? '+' : '-'}${formatMoney(tx.amount)}
        </div>
      `;
      familyTxListEl.appendChild(el);
    });
  }

  if (copyInviteBtn) {
    copyInviteBtn.addEventListener('click', () => {
      if (!familyInviteInput) return;
      navigator.clipboard.writeText(familyInviteInput.value).then(() => {
        if (copyToastEl) {
          copyToastEl.classList.remove('hidden');
          setTimeout(() => copyToastEl.classList.add('hidden'), 2500);
        }
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
      }).catch(() => {
        familyInviteInput.select();
        document.execCommand('copy');
        if (copyToastEl) {
          copyToastEl.classList.remove('hidden');
          setTimeout(() => copyToastEl.classList.add('hidden'), 2500);
        }
      });
    });
  }

  if (shareInviteBtn) {
    shareInviteBtn.addEventListener('click', () => {
      if (!familyInviteInput) return;
      const url = familyInviteInput.value;
      const text = encodeURIComponent('Привет! Давай вести совместный семейный бюджет в Smart Bujet:');
      const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${text}`;
      if (tg?.openTelegramLink) tg.openTelegramLink(shareUrl);
      else window.open(shareUrl, '_blank');
    });
  }

  if (retryFamilyBtn) {
    retryFamilyBtn.addEventListener('click', () => {
      fetchFamilySummary();
    });
  }

  if (refreshFamilyBtn) {
    refreshFamilyBtn.addEventListener('click', () => {
      fetchFamilySummary();
    });
  }

  if (leaveFamilyBtn) {
    leaveFamilyBtn.addEventListener('click', async () => {
      if (!confirm('Вы уверены, что хотите выйти из семейной группы? Совместный бюджет больше не будет синхронизироваться.')) return;
      try {
        const res = await fetch('/api/v1/family/leave', { method: 'POST', headers: getHeaders() });
        if (res.ok) {
          await fetchFamilySummary();
        } else {
          alert('Не удалось покинуть группу');
        }
      } catch (e) {
        alert('Ошибка соединения с сервером');
      }
    });
  }

  refreshBtn.addEventListener('click', () => {
    fetchProfile();
    fetchTransactions();
    fetchAssets();
  });

  // Check URL params for deep linking (e.g. ?page=deposits, ?page=family)
  const urlParams = new URLSearchParams(window.location.search);
  const initialPage = urlParams.get('page') || window.location.hash.replace('#', '');

  // Initial load
  fetchProfile().then(() => {
    fetchTransactions();
    if (initialPage === 'deposits' || initialPage === 'assets') {
      switchTab('tab-assets');
    } else if (initialPage === 'family' || initialPage === 'fam') {
      switchTab('tab-family');
    }
  });
})();
