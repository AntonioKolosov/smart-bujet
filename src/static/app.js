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

  // Theme Detection (Dark vs High-Contrast Light)
  function isColorLight(hex) {
    if (!hex) return false;
    const clean = hex.replace('#', '');
    if (clean.length !== 6) return false;
    const r = parseInt(clean.substring(0, 2), 16);
    const g = parseInt(clean.substring(2, 4), 16);
    const b = parseInt(clean.substring(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 160;
  }

  function applyTheme() {
    let isLight = false;
    if (tg?.colorScheme === 'light') {
      isLight = true;
    } else if (tg?.colorScheme === 'dark') {
      isLight = false;
    } else if (tg?.themeParams?.bg_color) {
      isLight = isColorLight(tg.themeParams.bg_color);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      isLight = true;
    }

    if (isLight) {
      document.body.classList.add('theme-light');
      document.body.classList.remove('theme-dark');
    } else {
      document.body.classList.add('theme-dark');
      document.body.classList.remove('theme-light');
    }
  }

  applyTheme();
  if (tg?.onEvent) {
    tg.onEvent('themeChanged', () => {
      applyTheme();
      if (tabAnalytics && tabAnalytics.classList.contains('active')) {
        fetchAnalytics(currentAnalyticsMode === 'family');
      }
    });
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
  const navCreditsBtn = document.getElementById('navCreditsBtn');
  const navAnalyticsBtn = document.getElementById('navAnalyticsBtn');
  const tabOps = document.getElementById('tab-operations');
  const tabAssets = document.getElementById('tab-assets');
  const tabCredits = document.getElementById('tab-credits');
  const tabAnalytics = document.getElementById('tab-analytics');

  // Operations Mode Switcher Elements
  const btnOpsPersonal = document.getElementById('btnOpsPersonal');
  const btnOpsFamily = document.getElementById('btnOpsFamily');
  const opsPersonalView = document.getElementById('opsPersonalView');
  const opsFamilyView = document.getElementById('opsFamilyView');

  // Analytics Tab Elements
  const btnAnalyticsPersonal = document.getElementById('btnAnalyticsPersonal');
  const btnAnalyticsFamily = document.getElementById('btnAnalyticsFamily');
  const analyticsLoaderEl = document.getElementById('analyticsLoader');
  const analyticsErrorEl = document.getElementById('analyticsError');
  const analyticsContentEl = document.getElementById('analyticsContent');
  const analyticsMonthSpendEl = document.getElementById('analyticsMonthSpend');
  const analyticsAvgSpendEl = document.getElementById('analyticsAvgSpend');
  const analyticsTopCategoryEl = document.getElementById('analyticsTopCategory');
  const analyticsCategoryPeriodEl = document.getElementById('analyticsCategoryPeriod');
  const donutChartContainer = document.getElementById('donutChartContainer');
  const categoryLegendList = document.getElementById('categoryLegendList');
  const barChartContainer = document.getElementById('barChartContainer');

  let currentOpsMode = 'personal';
  let currentAnalyticsMode = 'personal';

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

  // DOM Elements - Credits Tab
  const totalCreditDebtEl = document.getElementById('totalCreditDebt');
  const activeCreditsCountEl = document.getElementById('activeCreditsCount');
  const monthlyPaymentsTotalEl = document.getElementById('monthlyPaymentsTotal');
  const creditsListEl = document.getElementById('creditsList');
  const creditsLoaderEl = document.getElementById('creditsLoader');
  const creditsEmptyEl = document.getElementById('creditsEmpty');
  const addCreditBtn = document.getElementById('addCreditBtn');

  // DOM Elements - Credits Modals
  const addCreditModal = document.getElementById('addCreditModal');
  const closeAddCreditModalBtn = document.getElementById('closeAddCreditModalBtn');
  const addCreditForm = document.getElementById('addCreditForm');
  const addCreditModalErrorEl = document.getElementById('addCreditModalError');
  const creditNameInput = document.getElementById('creditNameInput');
  const creditBankInput = document.getElementById('creditBankInput');
  const creditCurrencySelect = document.getElementById('creditCurrencySelect');
  const creditAmountInput = document.getElementById('creditAmountInput');
  const creditPaymentInput = document.getElementById('creditPaymentInput');

  const repayCreditModal = document.getElementById('repayCreditModal');
  const closeRepayCreditModalBtn = document.getElementById('closeRepayCreditModalBtn');
  const repayCreditForm = document.getElementById('repayCreditForm');
  const repayCreditModalTitle = document.getElementById('repayCreditModalTitle');
  const repayCreditIdInput = document.getElementById('repayCreditId');
  const repayCreditAmountInput = document.getElementById('repayCreditAmountInput');
  const repayCreditModalErrorEl = document.getElementById('repayCreditModalError');

  // DOM Elements - Edit Transaction Modal & Category Picker Sheet
  const editTxModal = document.getElementById('editTxModal');
  const closeEditTxModalBtn = document.getElementById('closeEditTxModalBtn');
  const cancelEditTxBtn = document.getElementById('cancelEditTxBtn');
  const editTxForm = document.getElementById('editTxForm');
  const editTxModalError = document.getElementById('editTxModalError');
  const editTxIdInput = document.getElementById('editTxId');
  const editTxTypeInput = document.getElementById('editTxType');
  const editTxCategoryValue = document.getElementById('editTxCategoryValue');
  const editTxTitleDisplay = document.getElementById('editTxTitleDisplay');
  const editTxDateDisplay = document.getElementById('editTxDateDisplay');
  const editTxTypeBadge = document.getElementById('editTxTypeBadge');
  const editTxCurrencyLabel = document.getElementById('editTxCurrencyLabel');
  const editTxAmount = document.getElementById('editTxAmount');
  const saveEditTxBtn = document.getElementById('saveEditTxBtn');
  const deleteEditTxBtn = document.getElementById('deleteEditTxBtn');

  // Category Picker Sheet Elements
  const categoryPickerTrigger = document.getElementById('categoryPickerTrigger');
  const selectedCategoryDot = document.getElementById('selectedCategoryDot');
  const selectedCategoryIcon = document.getElementById('selectedCategoryIcon');
  const selectedCategoryName = document.getElementById('selectedCategoryName');
  const categorySheetOverlay = document.getElementById('categorySheetOverlay');
  const closeCategorySheetBtn = document.getElementById('closeCategorySheetBtn');
  const categorySearchInput = document.getElementById('categorySearchInput');
  const categorySheetList = document.getElementById('categorySheetList');

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

  // --- Tab Navigation & Mode Switchers ---
  function switchTab(tabId) {
    [tabOps, tabAssets, tabCredits, tabAnalytics].forEach(t => t && t.classList.remove('active'));
    [navOpsBtn, navAssetsBtn, navCreditsBtn, navAnalyticsBtn].forEach(b => b && b.classList.remove('active'));

    if (tabId === 'tab-analytics') {
      if (tabAnalytics) tabAnalytics.classList.add('active');
      if (navAnalyticsBtn) navAnalyticsBtn.classList.add('active');
      fetchAnalytics(currentAnalyticsMode === 'family');
    } else if (tabId === 'tab-assets') {
      if (tabAssets) tabAssets.classList.add('active');
      if (navAssetsBtn) navAssetsBtn.classList.add('active');
      fetchAssets();
    } else if (tabId === 'tab-credits') {
      if (tabCredits) tabCredits.classList.add('active');
      if (navCreditsBtn) navCreditsBtn.classList.add('active');
      fetchCredits();
    } else {
      if (tabOps) tabOps.classList.add('active');
      if (navOpsBtn) navOpsBtn.classList.add('active');
      if (currentOpsMode === 'family') {
        fetchFamilySummary();
      } else {
        fetchTransactions();
      }
    }
  }

  function switchOpsMode(mode) {
    currentOpsMode = mode;
    if (mode === 'family') {
      btnOpsPersonal?.classList.remove('active');
      btnOpsFamily?.classList.add('active');
      opsPersonalView?.classList.add('hidden');
      opsFamilyView?.classList.remove('hidden');
      fetchFamilySummary();
    } else {
      btnOpsFamily?.classList.remove('active');
      btnOpsPersonal?.classList.add('active');
      opsFamilyView?.classList.add('hidden');
      opsPersonalView?.classList.remove('hidden');
      fetchTransactions();
    }
  }

  function switchAnalyticsMode(mode) {
    currentAnalyticsMode = mode;
    if (mode === 'family') {
      btnAnalyticsPersonal?.classList.remove('active');
      btnAnalyticsFamily?.classList.add('active');
      fetchAnalytics(true);
    } else {
      btnAnalyticsFamily?.classList.remove('active');
      btnAnalyticsPersonal?.classList.add('active');
      fetchAnalytics(false);
    }
  }

  if (btnOpsPersonal) btnOpsPersonal.addEventListener('click', () => switchOpsMode('personal'));
  if (btnOpsFamily) btnOpsFamily.addEventListener('click', () => switchOpsMode('family'));
  if (btnAnalyticsPersonal) btnAnalyticsPersonal.addEventListener('click', () => switchAnalyticsMode('personal'));
  if (btnAnalyticsFamily) btnAnalyticsFamily.addEventListener('click', () => switchAnalyticsMode('family'));

  if (navOpsBtn) navOpsBtn.addEventListener('click', () => switchTab('tab-operations'));
  if (navAssetsBtn) navAssetsBtn.addEventListener('click', () => switchTab('tab-assets'));
  if (navCreditsBtn) navCreditsBtn.addEventListener('click', () => switchTab('tab-credits'));
  if (navAnalyticsBtn) navAnalyticsBtn.addEventListener('click', () => switchTab('tab-analytics'));

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

        const actionsWrap = document.createElement('div');
        actionsWrap.className = 'tx-card-actions';
        actionsWrap.appendChild(amounts);

        // Edit button - ONLY IN PERSONAL MODE
        if (currentOpsMode === 'personal') {
          const editBtn = document.createElement('button');
          editBtn.className = 'tx-edit-btn';
          editBtn.title = 'Редактировать операцию';
          editBtn.setAttribute('aria-label', 'Редактировать операцию');
          editBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          `;
          editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openEditModal(tx);
          });
          actionsWrap.appendChild(editBtn);
        }

        card.appendChild(info);
        card.appendChild(actionsWrap);
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

  // --- Credits Logic ---
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function fetchCredits() {
    if (creditsLoaderEl) creditsLoaderEl.classList.remove('hidden');
    if (creditsEmptyEl) creditsEmptyEl.classList.add('hidden');
    if (creditsListEl) creditsListEl.innerHTML = '';

    try {
      const [sumRes, listRes] = await Promise.all([
        fetch('/api/v1/credits/summary', { headers: getHeaders() }),
        fetch('/api/v1/credits/', { headers: getHeaders() })
      ]);

      if (sumRes.ok) {
        const sumData = await sumRes.json();
        if (totalCreditDebtEl) totalCreditDebtEl.textContent = formatMoney(sumData.total_debt);
        if (activeCreditsCountEl) activeCreditsCountEl.textContent = sumData.active_credits_count;
        if (monthlyPaymentsTotalEl) monthlyPaymentsTotalEl.textContent = formatMoney(sumData.total_monthly_payment);
      }

      if (listRes.ok) {
        const credits = await listRes.json();
        renderCredits(credits);
      }
    } catch (err) {
      console.error('Failed to load credits:', err);
    } finally {
      if (creditsLoaderEl) creditsLoaderEl.classList.add('hidden');
    }
  }

  function renderCredits(credits) {
    if (!creditsListEl) return;
    creditsListEl.innerHTML = '';

    if (!credits || credits.length === 0) {
      if (creditsEmptyEl) creditsEmptyEl.classList.remove('hidden');
      return;
    }
    if (creditsEmptyEl) creditsEmptyEl.classList.add('hidden');

    credits.forEach(cr => {
      const card = document.createElement('div');
      card.className = `credit-item ${cr.is_active ? '' : 'closed'}`;

      const orig = Number(cr.original_amount) || 0;
      const rem = Number(cr.remaining_amount) || 0;
      const repaid = Math.max(0, orig - rem);
      const pct = orig > 0 ? Math.min(100, Math.round((repaid / orig) * 100)) : (cr.is_active ? 0 : 100);

      card.innerHTML = `
        <div class="credit-header">
          <div class="credit-name-box">
            <span class="credit-title">${escapeHtml(cr.name)}</span>
            ${cr.bank_name ? `<span class="credit-bank">${escapeHtml(cr.bank_name)}</span>` : ''}
          </div>
          <span class="credit-badge ${cr.is_active ? 'active' : 'paid'}">
            ${cr.is_active ? 'Активен' : 'Выплачен 🎉'}
          </span>
        </div>
        <div class="credit-amounts-row">
          <div>
            <div class="credit-remaining ${cr.is_active ? '' : 'paid'}">${formatMoney(rem, cr.currency)}</div>
            <div class="credit-original">из ${formatMoney(orig, cr.currency)} (${pct}% выплачено)</div>
          </div>
        </div>
        <div class="credit-progress-wrap">
          <div class="credit-progress-bar" style="width: ${pct}%"></div>
        </div>
        <div class="credit-actions-row">
          <span class="credit-details-text">
            ${cr.monthly_payment ? `Платёж: ${formatMoney(cr.monthly_payment, cr.currency)}/мес` : ''}
          </span>
          ${cr.is_active ? `<button class="credit-repay-btn" data-id="${cr.id}">Внести платёж</button>` : ''}
        </div>
      `;

      const repayBtn = card.querySelector('.credit-repay-btn');
      if (repayBtn) {
        repayBtn.addEventListener('click', () => openRepayCreditModal(cr));
      }

      creditsListEl.appendChild(card);
    });
  }

  function openRepayCreditModal(credit) {
    if (!repayCreditModal) return;
    repayCreditIdInput.value = credit.id;
    repayCreditAmountInput.value = '';
    if (repayCreditModalTitle) repayCreditModalTitle.textContent = `Платёж: ${credit.name}`;
    if (repayCreditModalErrorEl) repayCreditModalErrorEl.classList.add('hidden');
    repayCreditModal.classList.remove('hidden');
    repayCreditAmountInput.focus();
  }

  if (closeRepayCreditModalBtn) {
    closeRepayCreditModalBtn.addEventListener('click', () => {
      if (repayCreditModal) repayCreditModal.classList.add('hidden');
    });
  }

  if (repayCreditForm) {
    repayCreditForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const creditId = repayCreditIdInput.value;
      const amount = Number(repayCreditAmountInput.value);

      if (!amount || amount <= 0) {
        if (repayCreditModalErrorEl) {
          repayCreditModalErrorEl.textContent = 'Укажите корректную сумму платежа';
          repayCreditModalErrorEl.classList.remove('hidden');
        }
        return;
      }

      const submitBtn = document.getElementById('repayCreditSubmitBtn');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Обработка...';
      }

      try {
        const res = await fetch(`/api/v1/credits/${creditId}/repay`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({ amount })
        });
        if (res.ok) {
          repayCreditModal.classList.add('hidden');
          repayCreditForm.reset();
          await fetchCredits();
          await fetchProfile();
          await fetchTransactions();
        } else {
          const err = await res.json().catch(() => ({}));
          if (repayCreditModalErrorEl) {
            repayCreditModalErrorEl.textContent = err.detail || 'Ошибка проведения платежа';
            repayCreditModalErrorEl.classList.remove('hidden');
          }
        }
      } catch (err) {
        if (repayCreditModalErrorEl) {
          repayCreditModalErrorEl.textContent = 'Ошибка соединения с сервером';
          repayCreditModalErrorEl.classList.remove('hidden');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Внести платёж';
        }
      }
    });
  }

  if (addCreditBtn) {
    addCreditBtn.addEventListener('click', () => {
      if (!addCreditModal) return;
      addCreditForm.reset();
      if (creditCurrencySelect) creditCurrencySelect.value = userCurrency;
      if (addCreditModalErrorEl) addCreditModalErrorEl.classList.add('hidden');
      addCreditModal.classList.remove('hidden');
      if (creditNameInput) creditNameInput.focus();
    });
  }

  if (closeAddCreditModalBtn) {
    closeAddCreditModalBtn.addEventListener('click', () => {
      if (addCreditModal) addCreditModal.classList.add('hidden');
    });
  }

  if (addCreditForm) {
    addCreditForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = creditNameInput.value.trim();
      const bank_name = creditBankInput.value.trim() || null;
      const currency = creditCurrencySelect.value;
      const original_amount = Number(creditAmountInput.value);
      const monthly_payment = creditPaymentInput.value ? Number(creditPaymentInput.value) : null;

      if (!name || !original_amount || original_amount <= 0) {
        if (addCreditModalErrorEl) {
          addCreditModalErrorEl.textContent = 'Укажите название и корректную сумму кредита';
          addCreditModalErrorEl.classList.remove('hidden');
        }
        return;
      }

      const submitBtn = document.getElementById('addCreditSubmitBtn');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Создание...';
      }

      try {
        const res = await fetch('/api/v1/credits/', {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({
            name,
            bank_name,
            currency,
            original_amount,
            monthly_payment
          })
        });

        if (res.ok) {
          addCreditModal.classList.add('hidden');
          addCreditForm.reset();
          await fetchCredits();
        } else {
          const err = await res.json().catch(() => ({}));
          if (addCreditModalErrorEl) {
            addCreditModalErrorEl.textContent = err.detail || 'Не удалось создать кредит';
            addCreditModalErrorEl.classList.remove('hidden');
          }
        }
      } catch (err) {
        if (addCreditModalErrorEl) {
          addCreditModalErrorEl.textContent = 'Ошибка соединения с сервером';
          addCreditModalErrorEl.classList.remove('hidden');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Создать кредит';
        }
      }
    });
  }

  // --- Category UI Meta (Синхронизировано с бэкендом) ---
  const CATEGORY_META = {
    'Еда вне дома': { icon: '🍽️', color: '#f97316' },
    'Продукты': { icon: '🛒', color: '#22c55e' },
    'Транспорт': { icon: '🚕', color: '#38bdf8' },
    'Развлечения': { icon: '🎉', color: '#a855f7' },
    'Здоровье': { icon: '💊', color: '#ec4899' },
    'Обязательные расходы': { icon: '⚡', color: '#eab308' },
    'Подписки': { icon: '📱', color: '#6366f1' },
    'Ребёнок': { icon: '👶', color: '#14b8a6' },
    'Питомец': { icon: '🐾', color: '#84cc16' },
    'Образование': { icon: '📚', color: '#06b6d4' },
    'Подарок': { icon: '🎁', color: '#f43f5e' },
    'Ремонт': { icon: '🛠️', color: '#f59e0b' },
    'Шоппинг': { icon: '🛍️', color: '#d946ef' },
    'Прочее': { icon: '📦', color: '#94a3b8' },
    'Погашение кредита': { icon: '💳', color: '#ef4444' },
    'Денежный перевод': { icon: '💸', color: '#8b5cf6' },
    'Зарплата': { icon: '💰', color: '#10b981' },
    'Проценты по вкладу': { icon: '📈', color: '#3b82f6' }
  };

  function getCategoryMeta(name) {
    return CATEGORY_META[name] || { icon: '🏷️', color: '#38bdf8' };
  }

  // --- Category Caching & Custom Bottom Sheet Category Picker ---
  const cachedCategoriesByType = {};
  let currentModalCategories = [];

  function setCategoryPickerSelection(catId, catName) {
    if (editTxCategoryValue) editTxCategoryValue.value = catId || '';
    if (selectedCategoryName) selectedCategoryName.textContent = catName || 'Выберите категорию';
    const meta = getCategoryMeta(catName);
    if (selectedCategoryIcon) selectedCategoryIcon.textContent = meta.icon;
    if (selectedCategoryDot) selectedCategoryDot.style.backgroundColor = meta.color;
  }

  function openCategorySheet() {
    if (!categorySheetOverlay) return;
    renderCategorySheetList(currentModalCategories);
    if (categorySearchInput) categorySearchInput.value = '';
    categorySheetOverlay.classList.remove('hidden');
    if (categorySearchInput) setTimeout(() => categorySearchInput.focus(), 80);
  }

  function closeCategorySheet() {
    if (!categorySheetOverlay) return;
    categorySheetOverlay.classList.add('hidden');
  }

  function renderCategorySheetList(categories) {
    if (!categorySheetList) return;
    categorySheetList.innerHTML = '';
    const selectedId = Number(editTxCategoryValue?.value);

    categories.forEach(cat => {
      const meta = getCategoryMeta(cat.name);
      const isSelected = cat.id === selectedId;
      const item = document.createElement('div');
      item.className = `category-sheet-item ${isSelected ? 'selected' : ''}`;
      item.innerHTML = `
        <span class="sheet-item-icon">${meta.icon}</span>
        <span class="sheet-item-name">${escapeHtml(cat.name)}</span>
        ${isSelected ? '<span class="sheet-item-check">✓</span>' : ''}
      `;
      item.addEventListener('click', () => {
        if (tg?.HapticFeedback?.selectionChanged) {
          tg.HapticFeedback.selectionChanged();
        }
        setCategoryPickerSelection(cat.id, cat.name);
        closeCategorySheet();
      });
      categorySheetList.appendChild(item);
    });
  }

  if (categorySearchInput) {
    categorySearchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = currentModalCategories.filter(c => c.name.toLowerCase().includes(q));
      renderCategorySheetList(filtered);
    });
  }

  if (categoryPickerTrigger) categoryPickerTrigger.addEventListener('click', openCategorySheet);
  if (closeCategorySheetBtn) closeCategorySheetBtn.addEventListener('click', closeCategorySheet);
  if (categorySheetOverlay) {
    categorySheetOverlay.addEventListener('click', (e) => {
      if (e.target === categorySheetOverlay) closeCategorySheet();
    });
  }

  async function fetchCategories(type) {
    const normType = type === 'income' ? 'income' : 'expense';
    if (cachedCategoriesByType[normType]) {
      return cachedCategoriesByType[normType];
    }
    const res = await fetch(`/api/v1/categories/?type=${normType}`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Не удалось загрузить категории');
    const categories = await res.json();
    cachedCategoriesByType[normType] = categories;
    return categories;
  }

  async function openEditModal(tx) {
    if (!editTxModal) return;
    if (editTxModalError) {
      editTxModalError.classList.add('hidden');
      editTxModalError.textContent = '';
    }

    editTxIdInput.value = tx.id;
    editTxTypeInput.value = tx.type;
    editTxTitleDisplay.textContent = tx.item_name || tx.category_name || 'Операция';
    editTxDateDisplay.textContent = `${formatDateGroup(tx.transaction_date)} • ${formatTime(tx.transaction_date)}`;

    if (editTxCurrencyLabel) {
      editTxCurrencyLabel.textContent = currencySymbol;
    }

    if (editTxTypeBadge) {
      const isInc = tx.type === 'income';
      editTxTypeBadge.textContent = isInc ? 'Доход' : 'Расход';
      editTxTypeBadge.className = `edit-tx-type-badge ${isInc ? 'income' : 'expense'}`;
    }

    editTxAmount.value = parseFloat(tx.amount).toFixed(2);
    setCategoryPickerSelection(tx.category_id, tx.category_name);

    try {
      const categories = await fetchCategories(tx.type);
      currentModalCategories = [...categories];

      // If current category is not in the list, prepend it
      if (tx.category_id && !currentModalCategories.some(c => c.id === tx.category_id) && tx.category_name) {
        currentModalCategories.unshift({ id: tx.category_id, name: tx.category_name });
      }
    } catch (e) {
      if (editTxModalError) {
        editTxModalError.textContent = e.message || 'Ошибка загрузки категорий';
        editTxModalError.classList.remove('hidden');
      }
    }

    editTxModal.classList.remove('hidden');
    setTimeout(() => editTxAmount.focus(), 80);
  }

  function closeEditModal() {
    if (!editTxModal) return;
    editTxModal.classList.add('hidden');
    editTxForm?.reset();
    closeCategorySheet();
  }

  if (closeEditTxModalBtn) closeEditTxModalBtn.addEventListener('click', closeEditModal);
  if (cancelEditTxBtn) cancelEditTxBtn.addEventListener('click', closeEditModal);
  if (editTxModal) {
    editTxModal.addEventListener('click', (e) => {
      if (e.target === editTxModal) closeEditModal();
    });
  }

  // Универсальное закрытие ВСЕХ модальных окон по клику на фон
  [addAssetModal, actionModal, addCreditModal, repayCreditModal].forEach(modalEl => {
    if (modalEl) {
      modalEl.addEventListener('click', (e) => {
        if (e.target === modalEl) modalEl.classList.add('hidden');
      });
    }
  });

  if (editTxForm) {
    editTxForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const txId = editTxIdInput.value;
      const amountVal = parseFloat(editTxAmount.value);
      const catIdVal = parseInt(editTxCategoryValue.value, 10);

      if (isNaN(amountVal) || amountVal <= 0) {
        if (editTxModalError) {
          editTxModalError.textContent = 'Укажите сумму больше 0';
          editTxModalError.classList.remove('hidden');
        }
        return;
      }

      if (saveEditTxBtn) {
        saveEditTxBtn.disabled = true;
        saveEditTxBtn.textContent = 'Сохранение...';
      }
      if (editTxModalError) editTxModalError.classList.add('hidden');

      try {
        const payload = {
          amount: amountVal,
          category_id: isNaN(catIdVal) ? null : catIdVal
        };

        const res = await fetch(`/api/v1/transactions/${txId}`, {
          method: 'PATCH',
          headers: getHeaders(),
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Ошибка обновления (${res.status})`);
        }

        if (tg?.HapticFeedback?.notificationOccurred) {
          tg.HapticFeedback.notificationOccurred('success');
        }

        closeEditModal();
        await Promise.all([fetchTransactions(), fetchProfile()]);
      } catch (err) {
        if (editTxModalError) {
          editTxModalError.textContent = err.message || 'Не удалось обновить операцию';
          editTxModalError.classList.remove('hidden');
        }
      } finally {
        if (saveEditTxBtn) {
          saveEditTxBtn.disabled = false;
          saveEditTxBtn.textContent = 'Сохранить';
        }
      }
    });
  }

  // --- Логика удаления транзакции ---
  if (deleteEditTxBtn) {
    deleteEditTxBtn.addEventListener('click', async () => {
      const txId = editTxIdInput.value;
      if (!txId) return;

      const confirmPrompt = 'Вы уверены, что хотите удалить эту операцию? Это действие необратимо.';

      const proceedDelete = async () => {
        deleteEditTxBtn.disabled = true;
        const originalHtml = deleteEditTxBtn.innerHTML;
        deleteEditTxBtn.innerHTML = '<span>Удаление...</span>';
        if (editTxModalError) editTxModalError.classList.add('hidden');

        try {
          const res = await fetch(`/api/v1/transactions/${txId}`, {
            method: 'DELETE',
            headers: getHeaders()
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Ошибка удаления (${res.status})`);
          }

          if (tg?.HapticFeedback?.notificationOccurred) {
            tg.HapticFeedback.notificationOccurred('success');
          }

          closeEditModal();
          await Promise.all([fetchTransactions(), fetchProfile()]);
        } catch (err) {
          if (editTxModalError) {
            editTxModalError.textContent = err.message || 'Не удалось удалить операцию';
            editTxModalError.classList.remove('hidden');
          }
          if (tg?.HapticFeedback?.notificationOccurred) {
            tg.HapticFeedback.notificationOccurred('error');
          }
        } finally {
          deleteEditTxBtn.disabled = false;
          deleteEditTxBtn.innerHTML = originalHtml;
        }
      };

      if (tg?.showConfirm) {
        tg.showConfirm(confirmPrompt, (confirmed) => {
          if (confirmed) {
            if (tg?.HapticFeedback?.impactOccurred) {
              tg.HapticFeedback.impactOccurred('medium');
            }
            proceedDelete();
          }
        });
      } else if (window.confirm(confirmPrompt)) {
        proceedDelete();
      }
    });
  }

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

  // --- Analytics Domain ---
  function formatCompact(num) {
    const val = Number(num) || 0;
    if (val >= 1000000) return (val / 1000000).toFixed(1).replace('.0', '') + 'M';
    if (val >= 1000) return Math.round(val / 1000) + 'k';
    return Math.round(val).toString();
  }

  async function fetchAnalytics(isFamily = false) {
    if (!tabAnalytics) return;
    analyticsLoaderEl?.classList.remove('hidden');
    analyticsErrorEl?.classList.add('hidden');
    analyticsContentEl?.classList.add('hidden');

    try {
      const familyParam = isFamily ? 'true' : 'false';
      const [catRes, monthRes] = await Promise.all([
        fetch(`/api/v1/analytics/categories?family=${familyParam}&period=month`, { headers: getHeaders() }),
        fetch(`/api/v1/analytics/monthly?family=${familyParam}&months=6`, { headers: getHeaders() })
      ]);

      if (!catRes.ok || !monthRes.ok) {
        throw new Error('Не удалось загрузить данные аналитики');
      }

      const catData = await catRes.json();
      const monthData = await monthRes.json();

      // Key Metrics
      const metrics = monthData.metrics || {};
      if (analyticsMonthSpendEl) {
        analyticsMonthSpendEl.textContent = formatMoney(metrics.current_month_spend || 0);
      }
      if (analyticsAvgSpendEl) {
        analyticsAvgSpendEl.textContent = formatMoney(metrics.monthly_average_spend || 0);
      }
      if (analyticsTopCategoryEl) {
        if (metrics.top_category_name && Number(metrics.top_category_amount) > 0) {
          analyticsTopCategoryEl.textContent = `${metrics.top_category_name} (${formatMoney(metrics.top_category_amount)})`;
        } else {
          analyticsTopCategoryEl.textContent = '—';
        }
      }

      if (analyticsCategoryPeriodEl && catData.period_label) {
        analyticsCategoryPeriodEl.textContent = catData.period_label;
      }

      // Charts
      renderDonutChart(catData.categories || [], catData.total_spend || 0);
      renderBarChart(monthData.history || []);

      analyticsContentEl?.classList.remove('hidden');
    } catch (err) {
      if (analyticsErrorEl) {
        analyticsErrorEl.textContent = err.message || 'Ошибка загрузки аналитики';
        analyticsErrorEl.classList.remove('hidden');
      }
    } finally {
      analyticsLoaderEl?.classList.add('hidden');
    }
  }

  function renderDonutChart(categories, totalSpend) {
    if (!donutChartContainer || !categoryLegendList) return;

    if (!categories || categories.length === 0 || Number(totalSpend) <= 0) {
      donutChartContainer.innerHTML = `
        <div class="empty-banner" style="padding: 24px 0;">
          <div class="empty-icon">📊</div>
          <p class="empty-title">Нет расходов за месяц</p>
          <span class="empty-desc">В этом месяце трат пока не зафиксировано</span>
        </div>`;
      categoryLegendList.innerHTML = '';
      return;
    }

    const radius = 70;
    const strokeWidth = 20;
    const circumference = 2 * Math.PI * radius; // ~439.82297
    let accumulatedOffset = 0;
    const hasMultiple = categories.length > 1;

    const isLight = document.body.classList.contains('theme-light');
    const trackColor = isLight ? 'rgba(15, 23, 42, 0.06)' : 'rgba(255, 255, 255, 0.05)';

    let circlesSvg = `
      <circle cx="100" cy="100" r="${radius}" fill="transparent" stroke="${trackColor}" stroke-width="${strokeWidth}" />
    `;

    categories.forEach(cat => {
      const pct = Math.max(0, Number(cat.percentage) || 0);
      const rawDash = (pct / 100) * circumference;
      const dash = hasMultiple ? Math.max(0.5, rawDash - 1.5) : rawDash;
      const offset = accumulatedOffset;

      circlesSvg += `
        <circle cx="100" cy="100" r="${radius}"
          fill="transparent"
          stroke="${cat.color || '#38bdf8'}"
          stroke-width="${strokeWidth}"
          stroke-dasharray="${dash} ${circumference - dash}"
          stroke-dashoffset="${-offset}"
          stroke-linecap="butt" />
      `;
      accumulatedOffset += rawDash;
    });

    donutChartContainer.innerHTML = `
      <svg width="200" height="200" viewBox="0 0 200 200" style="transform: rotate(-90deg); transform-origin: 50% 50%;">
        ${circlesSvg}
      </svg>
      <div class="donut-center-text">
        <span class="donut-center-total">${formatMoney(totalSpend)}</span>
        <span class="donut-center-sub">Всего трат</span>
      </div>
    `;

    categoryLegendList.innerHTML = categories.map(cat => `
      <div class="legend-item">
        <div class="legend-left">
          <span class="legend-color-dot" style="background: ${cat.color};"></span>
          <span class="legend-icon">${cat.icon || '🏷'}</span>
          <span class="legend-name">${escapeHtml(cat.name)}</span>
        </div>
        <div class="legend-right">
          <span class="legend-amount">${formatMoney(cat.amount)}</span>
          <span class="legend-pct">${(Number(cat.percentage) || 0).toFixed(1)}%</span>
        </div>
      </div>
    `).join('');
  }

  function renderBarChart(history) {
    if (!barChartContainer) return;
    if (!history || history.length === 0) {
      barChartContainer.innerHTML = `
        <div class="empty-banner" style="padding: 24px 0;">
          <p class="empty-title">Нет истории трат</p>
          <span class="empty-desc">Данные появятся по мере накопления расходов</span>
        </div>`;
      return;
    }

    const isLight = document.body.classList.contains('theme-light');
    const svgWidth = 330;
    const svgHeight = 160;
    const padTop = 26;
    const padBottom = 28;
    const padX = 10;
    const availWidth = svgWidth - padX * 2;
    const availHeight = svgHeight - padTop - padBottom;

    const maxExp = Math.max(...history.map(h => Number(h.total_expense) || 0), 100);
    const count = history.length;
    const slotWidth = availWidth / count;
    const barWidth = Math.min(30, Math.max(16, slotWidth * 0.6));

    const baselineColor = isLight ? 'rgba(15, 23, 42, 0.12)' : 'rgba(255, 255, 255, 0.1)';
    const amountColor = isLight ? '#0f172a' : '#cbd5e1';
    const labelColor = isLight ? '#334155' : '#94a3b8';
    const emptyBarColor = isLight ? 'rgba(15, 23, 42, 0.08)' : 'rgba(255, 255, 255, 0.15)';

    let barsSvg = '';
    history.forEach((item, idx) => {
      const exp = Number(item.total_expense) || 0;
      const barHeight = Math.max(exp > 0 ? 4 : 0, Math.round((exp / maxExp) * availHeight));
      const x = padX + idx * slotWidth + (slotWidth - barWidth) / 2;
      const y = svgHeight - padBottom - barHeight;

      const label = item.label || `${item.month}`;
      const amountText = exp > 0 ? formatCompact(exp) : '0';

      barsSvg += `
        <g class="bar-group">
          ${exp > 0 ? `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="url(#barGradient)" opacity="0.9" />` : `<rect x="${x}" y="${svgHeight - padBottom - 2}" width="${barWidth}" height="2" rx="1" fill="${emptyBarColor}" />`}
          <text x="${x + barWidth / 2}" y="${y - 6}" text-anchor="middle" fill="${amountColor}" font-size="10" font-weight="700">${amountText}</text>
          <text x="${x + barWidth / 2}" y="${svgHeight - 10}" text-anchor="middle" fill="${labelColor}" font-size="11" font-weight="600">${label}</text>
        </g>
      `;
    });

    const baselineY = svgHeight - padBottom;
    barChartContainer.innerHTML = `
      <svg width="100%" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="barGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#0284c7" />
          </linearGradient>
        </defs>
        <line x1="${padX}" y1="${baselineY}" x2="${svgWidth - padX}" y2="${baselineY}" stroke="${baselineColor}" stroke-width="1" />
        ${barsSvg}
      </svg>
    `;
  }

  refreshBtn.addEventListener('click', () => {
    fetchProfile();
    if (currentOpsMode === 'family') {
      fetchFamilySummary();
    } else {
      fetchTransactions();
    }
    fetchAssets();
    fetchCredits();
    if (tabAnalytics && tabAnalytics.classList.contains('active')) {
      fetchAnalytics(currentAnalyticsMode === 'family');
    }
  });

  // Check URL params for deep linking (e.g. ?page=deposits, ?page=family, ?page=credits, ?page=analytics)
  const urlParams = new URLSearchParams(window.location.search);
  const initialPage = (urlParams.get('page') || window.location.hash.replace('#', '') || '').toLowerCase();

  if (initialPage === 'deposits' || initialPage === 'assets') {
    switchTab('tab-assets');
  } else if (initialPage === 'credits' || initialPage === 'loans') {
    switchTab('tab-credits');
  } else if (initialPage === 'family' || initialPage === 'fam') {
    switchTab('tab-operations');
    switchOpsMode('family');
  } else if (initialPage === 'analytics' || initialPage === 'stats') {
    switchTab('tab-analytics');
  } else {
    switchTab('tab-operations');
  }

  // Always load user profile
  fetchProfile();
})();
