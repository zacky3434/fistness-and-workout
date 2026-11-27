(() => {
  let chatOpen = false;
  let chatMode = 'bot';
  let chatPollTimer = null;
  let devSelectedUid = null;
  let devMounted = false;

  // Interactive Spotlight Tour State
  let tourActive = false;
  let onboardingShownOnce = false;
  let tourStep = 0;

  // Marketplace State
  let storeCache = { products: [], my_orders: [] };
  let storeFilter = 'Semua';
  let storeSort = 'bestseller';
  let storeSearch = '';
  let onlyWishlist = false;
  let activeDetailProd = null;
  let detailQty = 1;
  let cart = JSON.parse(localStorage.getItem('kinetix_cart') || '[]');
  let wishlist = JSON.parse(localStorage.getItem('kinetix_wishlist') || '[]');
  let appliedVoucher = '';

  const esc = (s) => String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const rupiah = (n) => 'Rp ' + Number(n || 0).toLocaleString('id-ID');

  // 7 Langkah Panduan Langsung ke Elemen Asli (Spotlight Guided Tour)
  const TOUR_STEPS = [
    {
      tab: 'lab', selector: '#three-container', icon: 'box',
      title: '1. 3D Interactive Muscle Lab',
      desc: 'Coba geser layar untuk memutar tubuh 3D 360° dan klik ototnya langsung! Warna Toska berarti otot siap dilatih, Amber masa pemulihan, dan Merah butuh istirahat.',
      tip: 'Klik tombol Squat / Press / Curl di atas kanvas untuk melihat animasi gerakan 3D, atau unggah file .GLB milikmu!'
    },
    {
      tab: 'lab', selector: '#tab-lab .xl\\:col-span-5 > div:first-child', icon: 'sparkles',
      title: '2. Inspector Otot & Rekomendasi',
      desc: 'Setiap otot yang kamu klik di model 3D langsung memunculkan skor kelelahan dan 3 gerakan terbaik yang siap dicatat hanya dengan 1 klik tombol Log.',
      tip: 'Fokus latih otot berstatus "Fresh" agar hasil hipertrofi maksimal tanpa overtraining.'
    },
    {
      tab: 'programs', selector: '#program-cards', icon: 'layers',
      title: '3. Program & Split Latihan',
      desc: 'Tidak perlu bingung menyusun jadwal gym! Pilih split Push/Pull/Legs, Upper/Lower, Full Body, atau Home HIIT lalu langsung catat gerakannya.',
      tip: 'Pemula disarankan mulai dari Full Body 3x seminggu sebelum naik ke Push/Pull/Legs.'
    },
    {
      tab: 'log', selector: '#workout-form', icon: 'clipboard-list',
      title: '4. Catat Latihan & Deteksi PR',
      desc: 'Masukkan gerakan, set, repetisi, dan beban (kg) di form ini. Sistem otomatis menghitung total volume, kalori terbakar, streak, dan memberi notifikasi saat kamu memecahkan Rekor PR!',
      tip: 'Semua data latihan di sini bisa diekspor ke laporan Excel (.xlsx) lewat menu ☰ di kiri atas.'
    },
    {
      tab: 'tools', selector: '#tab-tools .grid > div:first-child', icon: 'timer',
      title: '5. HIIT Timer, 1RM & Plate Barbel',
      desc: 'Atur waktu istirahat antar-set atau interval HIIT lengkap dengan bunyi beep. Di sebelah kanannya tersedia kalkulator kekuatan maksimal 1RM dan susunan piringan barbel visual.',
      tip: 'Timer tetap berjalan di tombol melayang meski kamu berpindah ke tab lain!'
    },
    {
      tab: 'store', selector: '#store-marketplace-header', icon: 'shopping-bag',
      title: '6. Marketplace Minuman Kalsium & Suplemen',
      desc: 'Belanja minuman kalsium tulang, isotonik elektrolit, hingga whey protein seperti di marketplace! Ada fitur pencarian, wishlist ❤️, ulasan bintang, keranjang belanja, dan kode voucher.',
      tip: 'Pakai kode FIT10 (diskon 10%) atau KALSIUM10 (potongan Rp 10.000). Pembelian minuman otomatis menambah hidrasi harianmu!'
    },
    {
      tab: 'lab', selector: '#chat-fab', icon: 'bot',
      title: '7. AI Coach Bot & Live Customer Service',
      desc: 'Butuh saran otot yang siap dilatih, hitungan kalori, rekomendasi minuman kalsium, atau bantuan pesanan? Klik tombol chat ini kapan saja!',
      tip: 'Semua pemberitahuan penting juga selalu muncul rapi di ikon lonceng Notifikasi kanan atas.'
    }
  ];

  // Inject CSS khusus Spotlight Tour
  function injectTourStyles() {
    if (document.getElementById('kinetix-tour-style')) return;
    const st = document.createElement('style');
    st.id = 'kinetix-tour-style';
    st.textContent = `
      #tour-backdrop {
        position: fixed; inset: 0; z-index: 9996; background: transparent;
      }
      #tour-spotlight {
        position: fixed; z-index: 9997; pointer-events: none;
        border-radius: 22px; border: 2.5px solid #2DD4BF;
        box-shadow: 0 0 0 9999px rgba(4, 13, 18, 0.74), 0 0 32px rgba(45, 212, 191, 0.65);
        transition: top .38s cubic-bezier(.22,1,.36,1), left .38s cubic-bezier(.22,1,.36,1),
                    width .38s cubic-bezier(.22,1,.36,1), height .38s cubic-bezier(.22,1,.36,1);
        animation: spotPulse 2s ease-in-out infinite;
      }
      @keyframes spotPulse {
        0%, 100% { border-color: #2DD4BF; }
        50%      { border-color: #38BDF8; }
      }
      #tour-tooltip {
        position: fixed; z-index: 9999; width: min(92vw, 390px);
        transition: top .35s cubic-bezier(.22,1,.36,1), left .35s cubic-bezier(.22,1,.36,1), opacity .25s ease;
      }
    `;
    document.head.appendChild(st);
  }

  // 1. Mount UI User (Marketplace, Spotlight Tour, Chatbot/CS — ZERO elemen Developer)
  function mountUserUI() {
    injectTourStyles();
    const main = document.querySelector('main');
    const nav = document.querySelector('nav.anim-dock');
    if (!main || !nav) return;

    nav.classList.remove('grid-cols-5');
    nav.classList.add('grid-cols-6', 'max-w-3xl');

    const storeBtn = document.createElement('button');
    storeBtn.type = 'button';
    storeBtn.dataset.tab = 'store';
    storeBtn.className = 'dock-item py-2.5 px-2 rounded-2xl flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-toska/10';
    storeBtn.innerHTML = '<i data-lucide="shopping-bag" class="w-4 h-4 shrink-0"></i><span>Toko</span>';
    storeBtn.onclick = () => switchTab('store');
    nav.appendChild(storeBtn);

    // Tambah tombol "Panduan Interaktif" di Drawer (☰)
    const drawerMenu = document.querySelector('#side-drawer .space-y-2');
    if (drawerMenu) {
      const guideBtn = document.createElement('button');
      guideBtn.type = 'button';
      guideBtn.className = 'w-full flex items-center justify-between px-4 py-3 rounded-xl surface-inner hover:border-toska text-xs font-semibold';
      guideBtn.innerHTML = `
        <span class="flex items-center gap-2.5">
          <i data-lucide="compass" class="w-4 h-4 text-toska"></i>
          <span>Panduan Interaktif Fitur</span>
        </span>
        <i data-lucide="chevron-right" class="w-4 h-4 text-slate-400"></i>
      `;
      guideBtn.onclick = () => { toggleDrawer(false); startGuidedTour(0); };
      drawerMenu.appendChild(guideBtn);
    }

    // ============ TAB TOKO ALA MARKETPLACE ============
    const storeSec = document.createElement('section');
    storeSec.id = 'tab-store';
    storeSec.className = 'tab-panel hidden space-y-6';
    storeSec.innerHTML = `
      <!-- Promo Hero Banner Marketplace -->
      <div id="store-marketplace-header" class="relative overflow-hidden rounded-3xl p-6 sm:p-7 btn-gradient text-white shadow-xl">
        <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 text-[11px] font-bold mb-2">
              <i data-lucide="zap" class="w-3.5 h-3.5"></i> KINETIX FITNESS MARKETPLACE
            </span>
            <h2 class="text-2xl sm:text-3xl font-extrabold leading-tight">Minuman Kalsium & Nutrisi Olahraga</h2>
            <p class="text-xs sm:text-sm text-teal-50/90 mt-1 max-w-xl">
              Perkuat tulang, sendi, dan pemulihan otot dengan minuman kalsium & suplemen pilihan. Pembelian minuman otomatis mengisi progres hidrasi harianmu!
            </p>
            <div class="flex flex-wrap items-center gap-2 mt-3">
              <button type="button" onclick="window.copyVoucher('FIT10')" class="px-3 py-1.5 rounded-xl bg-white/20 hover:bg-white/30 text-[11px] font-bold backdrop-blur-sm">
                🎟️ FIT10 — Diskon 10% (Klik Salin)
              </button>
              <button type="button" onclick="window.copyVoucher('KALSIUM10')" class="px-3 py-1.5 rounded-xl bg-white/20 hover:bg-white/30 text-[11px] font-bold backdrop-blur-sm">
                🎟️ KALSIUM10 — Potongan Rp 10rb
              </button>
            </div>
          </div>

          <button type="button" onclick="window.toggleCartDrawer(true)" class="self-start md:self-center px-5 py-3.5 rounded-2xl bg-white text-teal-800 font-extrabold text-xs sm:text-sm flex items-center gap-2.5 shadow-xl hover:scale-105 transition shrink-0">
            <i data-lucide="shopping-cart" class="w-5 h-5 text-toska"></i>
            <span>Keranjang</span>
            <span id="store-cart-count" class="px-2 py-0.5 rounded-full bg-coral text-white text-xs font-extrabold">0</span>
          </button>
        </div>
      </div>

      <!-- Search, Category Pills, Sort & Wishlist Filter -->
      <div class="glass rounded-3xl p-5 space-y-4">
        <div class="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          <div class="relative flex-1">
            <i data-lucide="search" class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2"></i>
            <input id="mp-search" type="text" placeholder="Cari minuman kalsium, isotonik, whey protein..." class="field-input w-full pl-10 pr-4 py-2.5 rounded-xl text-xs sm:text-sm" />
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <select id="mp-sort" class="field-input px-3 py-2.5 rounded-xl text-xs font-semibold">
              <option value="bestseller">Urutkan: Terlaris</option>
              <option value="rating">Rating Tertinggi</option>
              <option value="cheap">Harga Termurah</option>
              <option value="expensive">Harga Termahal</option>
            </select>
            <button type="button" id="mp-wish-btn" onclick="window.toggleWishlistFilter()" class="px-3.5 py-2.5 rounded-xl surface-inner text-xs font-bold flex items-center gap-1.5 hover:border-rose-400">
              <i data-lucide="heart" class="w-4 h-4 text-rose-500"></i>
              <span>Favorit</span>
            </button>
          </div>
        </div>

        <div id="store-cat-filters" class="flex flex-wrap gap-1.5"></div>
        <div id="store-product-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 pt-1"></div>
      </div>

      <!-- Pelacakan Pesanan Customer -->
      <div class="glass rounded-3xl p-6">
        <h3 class="font-bold text-base mb-3 flex items-center gap-2">
          <i data-lucide="package" class="w-4 h-4 text-toska"></i> Lacak Pesanan Saya
        </h3>
        <div id="my-orders-list" class="space-y-3 text-xs"></div>
      </div>
    `;
    main.appendChild(storeSec);

    // ============ MODAL DETAIL PRODUK & ULASAN + DRAWER KERANJANG ============
    const overlays = document.createElement('div');
    overlays.innerHTML = `
      <!-- Detail Produk Modal -->
      <div id="prod-detail-modal" class="hidden fixed inset-0 z-50 bg-[#040D12]/75 backdrop-blur-sm flex items-center justify-center p-4">
        <div class="w-full max-w-2xl max-h-[90vh] overflow-y-auto glass rounded-3xl p-5 sm:p-6 relative anim-pop">
          <button type="button" onclick="window.closeProdDetail()" class="absolute top-4 right-4 p-2 rounded-xl surface-inner hover:border-toska z-10">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
          <div id="prod-detail-body"></div>
        </div>
      </div>

      <!-- Slide-Over Keranjang & Checkout -->
      <div id="cart-backdrop" onclick="window.toggleCartDrawer(false)" class="hidden fixed inset-0 z-50 bg-[#040D12]/65 backdrop-blur-sm"></div>
      <aside id="cart-drawer" class="fixed top-0 right-0 bottom-0 z-50 w-full max-w-md glass border-l p-5 flex flex-col justify-between translate-x-full transition-transform duration-300">
        <div class="flex items-center justify-between pb-3 border-b border-toska/15">
          <h3 class="font-extrabold text-base flex items-center gap-2">
            <i data-lucide="shopping-cart" class="w-5 h-5 text-toska"></i> Keranjang Belanja
          </h3>
          <button type="button" onclick="window.toggleCartDrawer(false)" class="p-2 rounded-xl surface-inner"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>

        <div id="cart-items-box" class="flex-1 overflow-y-auto py-4 space-y-3 text-xs"></div>

        <div class="pt-3 border-t border-toska/15 space-y-3 text-xs">
          <div class="flex gap-2">
            <input id="cart-voucher" type="text" placeholder="Kode voucher (FIT10 / KALSIUM10)" class="field-input flex-1 px-3 py-2 rounded-xl text-xs uppercase" />
            <button type="button" onclick="window.applyCartVoucher()" class="px-3.5 py-2 rounded-xl bg-toska/15 text-teal-700 dark:text-toskaBright font-bold hover:bg-toska hover:text-white">Pakai</button>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <select id="cart-shipping" onchange="window.renderCart()" class="field-input px-2.5 py-2 rounded-xl text-xs">
              <option value="Ambil di Gym">Ambil di Gym (Gratis)</option>
              <option value="Reguler" selected>Reguler (+Rp 8.000)</option>
              <option value="Express">Express (+Rp 15.000)</option>
            </select>
            <select id="cart-payment" class="field-input px-2.5 py-2 rounded-xl text-xs">
              <option value="QRIS">QRIS Instan</option>
              <option value="E-Wallet">GoPay / OVO / DANA</option>
              <option value="Transfer Bank">Transfer Bank</option>
              <option value="COD">Bayar di Tempat (COD)</option>
            </select>
          </div>
          <input id="cart-address" type="text" placeholder="Alamat pengiriman / catatan kurir..." class="field-input w-full px-3 py-2 rounded-xl text-xs" />

          <div class="p-3 rounded-2xl surface-inner space-y-1">
            <div class="flex justify-between text-slate-500"><span>Subtotal</span><span id="cart-sub">Rp 0</span></div>
            <div class="flex justify-between text-slate-500"><span>Ongkos Kirim</span><span id="cart-ship">Rp 0</span></div>
            <div class="flex justify-between text-emerald-600 dark:text-emerald-400"><span>Diskon Voucher</span><span id="cart-disc">-Rp 0</span></div>
            <div class="flex justify-between font-extrabold text-sm pt-1.5 border-t border-toska/15"><span>Total Bayar</span><span id="cart-total" class="toska-text">Rp 0</span></div>
          </div>

          <button type="button" onclick="window.submitCheckout()" class="w-full btn-gradient text-white font-bold py-3 rounded-xl text-sm shadow-lg">
            Checkout Sekarang
          </button>
        </div>
      </aside>

      <!-- Spotlight Guided Tour Elements -->
      <div id="tour-backdrop" class="hidden"></div>
      <div id="tour-spotlight" class="hidden"></div>
      <div id="tour-tooltip" class="hidden glass rounded-3xl p-5 shadow-2xl border-2 border-toska/40">
        <div class="flex items-center justify-between gap-2 mb-2.5">
          <span id="tt-step-badge" class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-toska/15 text-teal-700 dark:text-toskaBright">Langkah 1 / 7</span>
          <button type="button" id="tt-skip" class="text-[11px] font-semibold text-slate-400 hover:text-toska">Lewati</button>
        </div>
        <div class="flex items-start gap-3">
          <div id="tt-icon" class="w-10 h-10 rounded-xl btn-gradient text-white flex items-center justify-center shrink-0 shadow"></div>
          <div>
            <h4 id="tt-title" class="font-extrabold text-sm sm:text-base leading-snug"></h4>
            <p id="tt-desc" class="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed"></p>
          </div>
        </div>
        <div class="mt-3 p-2.5 rounded-xl bg-toska/10 border border-toska/25 text-[11px] text-teal-800 dark:text-teal-200 flex items-start gap-2">
          <span class="shrink-0">💡</span>
          <span id="tt-tip" class="leading-snug font-medium"></span>
        </div>
        <div class="flex items-center justify-between mt-4 pt-3 border-t border-toska/15">
          <div id="tt-dots" class="flex items-center gap-1.5"></div>
          <div class="flex items-center gap-2">
            <button type="button" id="tt-prev" class="px-3 py-1.5 rounded-xl surface-inner text-xs font-bold hover:border-toska">←</button>
            <button type="button" id="tt-next" class="btn-gradient text-white px-4 py-1.5 rounded-xl text-xs font-bold shadow">Lanjut →</button>
          </div>
        </div>
      </div>

      <!-- Floating AI Coach & Live CS Widget -->
      <button type="button" id="chat-fab" class="fixed bottom-24 right-5 z-40 btn-gradient text-white w-14 h-14 rounded-2xl shadow-2xl flex items-center justify-center hover:scale-105 transition" title="AI Coach & Customer Service">
        <i data-lucide="message-circle" class="w-6 h-6"></i>
      </button>

      <div id="chat-window" class="hidden fixed bottom-24 right-4 sm:right-6 z-50 w-[92vw] max-w-sm glass rounded-3xl overflow-hidden flex flex-col shadow-2xl anim-pop" style="height: 490px;">
        <div class="btn-gradient text-white px-4 py-3.5 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center"><i data-lucide="bot" class="w-5 h-5"></i></div>
            <div>
              <p class="text-sm font-extrabold leading-tight">KINETIX AI & CS</p>
              <p class="text-[10px] text-teal-100">Asisten Olahraga & Customer Service</p>
            </div>
          </div>
          <button type="button" id="chat-close-btn" class="p-1.5 rounded-lg bg-white/15 hover:bg-white/25"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>

        <div class="px-3 py-2 surface-inner border-b flex items-center gap-1.5">
          <button type="button" id="cm-bot" class="flex-1 py-1.5 rounded-xl text-[11px] font-bold bg-toska text-white">AI Chatbot</button>
          <button type="button" id="cm-cs" class="flex-1 py-1.5 rounded-xl text-[11px] font-semibold text-slate-600 dark:text-slate-300">Live CS</button>
        </div>

        <div id="chat-messages" class="flex-1 p-3.5 space-y-2.5 overflow-y-auto text-xs"></div>

        <div class="px-3 pb-2 flex gap-1.5 overflow-x-auto">
          <button type="button" class="quick-q shrink-0 px-2.5 py-1 rounded-full surface-inner text-[10px] font-semibold hover:border-toska" data-q="Rekomendasi minuman kalsium & voucher">Minuman kalsium?</button>
          <button type="button" class="quick-q shrink-0 px-2.5 py-1 rounded-full surface-inner text-[10px] font-semibold hover:border-toska" data-q="Otot apa yang siap dilatih hari ini?">Otot siap latih?</button>
          <button type="button" class="quick-q shrink-0 px-2.5 py-1 rounded-full surface-inner text-[10px] font-semibold hover:border-toska" data-q="Berapa target kalori dan protein saya?">Target kalori?</button>
          <button type="button" class="quick-q shrink-0 px-2.5 py-1 rounded-full surface-inner text-[10px] font-semibold hover:border-toska" data-q="Hubungi CS">Hubungi CS</button>
        </div>

        <form id="chat-form" class="p-3 border-t border-teal-500/15 flex gap-2">
          <input id="chat-input" type="text" placeholder="Tanya AI Coach atau CS..." class="field-input flex-1 px-3.5 py-2 rounded-xl text-xs" />
          <button type="submit" class="btn-gradient text-white px-3.5 py-2 rounded-xl flex items-center justify-center"><i data-lucide="send" class="w-4 h-4"></i></button>
        </form>
      </div>
    `;
    document.body.appendChild(overlays);

    const ft = document.getElementById('floating-timer');
    if (ft) { ft.classList.remove('bottom-24'); ft.classList.add('bottom-40'); }

    // Event bindings Marketplace
    document.getElementById('mp-search').addEventListener('input', (e) => { storeSearch = e.target.value.trim().toLowerCase(); renderStore(); });
    document.getElementById('mp-sort').addEventListener('change', (e) => { storeSort = e.target.value; renderStore(); });

    // Event bindings Spotlight Tour
    document.getElementById('tt-skip').onclick = () => stopGuidedTour(true);
    document.getElementById('tt-prev').onclick = () => { if (tourStep > 0) { tourStep--; showTourStep(); } };
    document.getElementById('tt-next').onclick = () => {
      if (tourStep < TOUR_STEPS.length - 1) { tourStep++; showTourStep(); }
      else stopGuidedTour(true);
    };
    window.addEventListener('resize', () => { if (tourActive) positionSpotlight(); });
    window.addEventListener('scroll', () => { if (tourActive) positionSpotlight(); }, { passive: true });

    // Event bindings Chat
    document.getElementById('chat-fab').onclick = () => toggleChat(true);
    document.getElementById('chat-close-btn').onclick = () => toggleChat(false);
    document.getElementById('cm-bot').onclick = () => setChatMode('bot');
    document.getElementById('cm-cs').onclick = () => setChatMode('cs');
    document.querySelectorAll('.quick-q').forEach(b => b.onclick = () => sendChat(b.dataset.q));
    document.getElementById('chat-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const inp = document.getElementById('chat-input');
      const txt = inp.value.trim();
      if (!txt) return;
      inp.value = '';
      sendChat(txt);
    });

    updateCartBadge();
    lucide.createIcons();
  }

  // ============ 2. INTERACTIVE SPOTLIGHT GUIDED TOUR ============
  function startGuidedTour(startIdx = 0) {
    tourActive = true;
    tourStep = startIdx;
    document.getElementById('tour-backdrop').classList.remove('hidden');
    document.getElementById('tour-spotlight').classList.remove('hidden');
    document.getElementById('tour-tooltip').classList.remove('hidden');
    showTourStep();
  }

  async function stopGuidedTour(markDone = false) {
    tourActive = false;
    document.getElementById('tour-backdrop').classList.add('hidden');
    document.getElementById('tour-spotlight').classList.add('hidden');
    document.getElementById('tour-tooltip').classList.add('hidden');
    if (markDone) {
      onboardingShownOnce = true;
      await fetch('/api/onboarding/complete', { method: 'POST', credentials: 'same-origin' });
      if (typeof appData !== 'undefined' && appData && appData.profile) appData.profile.onboarding_done = 1;
      showToast('Panduan selesai! Kamu bisa buka lagi lewat menu ☰.');
    }
  }

  function showTourStep() {
    const step = TOUR_STEPS[tourStep];
    if (typeof activeTab !== 'undefined' && activeTab !== step.tab) {
      window.switchTab(step.tab);
    }

    document.getElementById('tt-step-badge').textContent = `Panduan ${tourStep + 1} / ${TOUR_STEPS.length}`;
    document.getElementById('tt-icon').innerHTML = `<i data-lucide="${step.icon}" class="w-5 h-5"></i>`;
    document.getElementById('tt-title').textContent = step.title;
    document.getElementById('tt-desc').textContent = step.desc;
    document.getElementById('tt-tip').textContent = step.tip;
    document.getElementById('tt-prev').classList.toggle('invisible', tourStep === 0);
    document.getElementById('tt-next').textContent = tourStep === TOUR_STEPS.length - 1 ? 'Mulai Latihan! 🚀' : 'Lanjut →';
    document.getElementById('tt-dots').innerHTML = TOUR_STEPS.map((_, i) =>
      `<span class="h-1.5 rounded-full transition-all ${i === tourStep ? 'w-5 bg-toska' : 'w-1.5 bg-slate-400/40'}"></span>`
    ).join('');
    lucide.createIcons();

    setTimeout(() => {
      const target = document.querySelector(step.selector);
      if (target && getComputedStyle(target).position !== 'fixed') {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      setTimeout(positionSpotlight, 280);
    }, 120);
  }

  function positionSpotlight() {
    if (!tourActive) return;
    const step = TOUR_STEPS[tourStep];
    const target = document.querySelector(step.selector);
    const spot = document.getElementById('tour-spotlight');
    const tip = document.getElementById('tour-tooltip');

    if (!target) {
      spot.style.top = '50%'; spot.style.left = '50%'; spot.style.width = '0px'; spot.style.height = '0px';
      tip.style.top = '50%'; tip.style.left = '50%'; tip.style.transform = 'translate(-50%, -50%)';
      return;
    }

    const r = target.getBoundingClientRect();
    const pad = 8;
    const sTop = Math.max(8, r.top - pad);
    const sLeft = Math.max(8, r.left - pad);
    const sW = Math.min(window.innerWidth - 16, r.width + pad * 2);
    const sH = Math.min(window.innerHeight - 16, r.height + pad * 2);

    spot.style.top = `${sTop}px`;
    spot.style.left = `${sLeft}px`;
    spot.style.width = `${sW}px`;
    spot.style.height = `${sH}px`;

    tip.style.transform = 'none';
    const tipRect = tip.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;

    let tTop = sTop + sH + 14;
    if (tTop + tipRect.height > vh - 16) tTop = sTop - tipRect.height - 14;
    if (tTop < 16) tTop = Math.max(16, (vh - tipRect.height) / 2);

    let tLeft = sLeft + (sW - tipRect.width) / 2;
    tLeft = Math.max(12, Math.min(vw - tipRect.width - 12, tLeft));

    tip.style.top = `${tTop}px`;
    tip.style.left = `${tLeft}px`;
  }

  // ============ 3. MARKETPLACE FUNCTIONS ============
  async function loadStore() {
    const res = await fetch('/api/store/products', { credentials: 'same-origin' });
    if (!res.ok) return;
    storeCache = await res.json();
    renderStore();
  }

  function renderStore() {
    const cats = ['Semua', ...new Set(storeCache.products.map(p => p.category))];
    document.getElementById('store-cat-filters').innerHTML = cats.map(c => `
      <button type="button" onclick="window.setStoreFilter('${esc(c)}')" class="px-3.5 py-1.5 rounded-xl text-xs font-bold transition ${storeFilter === c ? 'btn-gradient text-white shadow' : 'surface-inner text-slate-600 dark:text-slate-300 hover:border-toska'}">${esc(c)}</button>
    `).join('');

    let items = storeCache.products.filter(p => {
      const matchCat = storeFilter === 'Semua' || p.category === storeFilter;
      const matchSearch = !storeSearch || p.name.toLowerCase().includes(storeSearch) || p.benefit.toLowerCase().includes(storeSearch) || p.category.toLowerCase().includes(storeSearch);
      const matchWish = !onlyWishlist || wishlist.includes(p.id);
      return matchCat && matchSearch && matchWish;
    });

    if (storeSort === 'cheap') items.sort((a, b) => a.price - b.price);
    else if (storeSort === 'expensive') items.sort((a, b) => b.price - a.price);
    else if (storeSort === 'rating') items.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    else items.sort((a, b) => (b.sold_count || 0) - (a.sold_count || 0));

    document.getElementById('store-product-grid').innerHTML = items.length ? items.map(p => {
      const discPct = p.original_price > p.price ? Math.round((1 - p.price / p.original_price) * 100) : 0;
      const isFav = wishlist.includes(p.id);
      return `
        <div class="surface-inner rounded-2xl overflow-hidden flex flex-col justify-between group hover:border-toska transition">
          <div class="relative h-44 bg-gradient-to-br from-[#0B2936] to-[#06131A] overflow-hidden cursor-pointer" onclick="window.openProdDetail(${p.id})">
            ${p.image_url ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500" onerror="this.style.display='none'" />` : ''}
            <div class="absolute inset-0 bg-gradient-to-t from-[#041017]/80 via-transparent to-transparent"></div>
            <div class="absolute top-2.5 left-2.5 flex items-center gap-1.5">
              ${discPct > 0 ? `<span class="px-2 py-0.5 rounded-lg bg-coral text-white text-[10px] font-extrabold">-${discPct}%</span>` : ''}
              <span class="px-2 py-0.5 rounded-lg bg-[#041017]/75 text-toskaBright text-[10px] font-bold backdrop-blur-sm">${esc(p.badge)}</span>
            </div>
            <button type="button" onclick="event.stopPropagation(); window.toggleWishlist(${p.id})" class="absolute top-2.5 right-2.5 w-8 h-8 rounded-full bg-white/85 dark:bg-[#041017]/80 flex items-center justify-center shadow hover:scale-110 transition">
              <i data-lucide="heart" class="w-4 h-4 ${isFav ? 'fill-rose-500 text-rose-500' : 'text-slate-500'}"></i>
            </button>
            <span class="absolute bottom-2.5 left-3 text-[10px] font-semibold text-teal-200">${esc(p.category)}${p.volume_ml ? ` • ${p.volume_ml}ml` : ''}</span>
          </div>

          <div class="p-4 flex-1 flex flex-col justify-between">
            <div class="cursor-pointer" onclick="window.openProdDetail(${p.id})">
              <h4 class="font-extrabold text-sm leading-snug group-hover:text-toska transition">${esc(p.name)}</h4>
              <div class="flex items-center gap-2 mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                <span class="inline-flex items-center gap-0.5 font-bold text-amber-500">★ ${(p.rating || 4.8).toFixed(1)}</span>
                <span>•</span>
                <span>Terjual ${p.sold_count || 0}+</span>
                <span>•</span>
                <span>Stok ${p.stock}</span>
              </div>
              <div class="mt-2.5 flex items-baseline gap-2">
                <span class="text-base font-extrabold toska-text">${rupiah(p.price)}</span>
                ${discPct > 0 ? `<span class="text-[11px] line-through text-slate-400">${rupiah(p.original_price)}</span>` : ''}
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 mt-4">
              <button type="button" onclick="window.openProdDetail(${p.id})" class="py-2 rounded-xl glass text-[11px] font-bold hover:border-toska">Detail</button>
              <button type="button" ${p.stock < 1 ? 'disabled' : ''} onclick="window.addToCart(${p.id}, 1)"
                      class="py-2 rounded-xl text-[11px] font-bold ${p.stock > 0 ? 'btn-gradient text-white shadow' : 'bg-slate-400/30 text-slate-400 cursor-not-allowed'}">
                ${p.stock > 0 ? '+ Keranjang' : 'Habis'}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('') : '<p class="col-span-full text-center text-xs text-slate-400 py-8">Produk tidak ditemukan. Coba kata kunci atau filter lain.</p>';

    const statusBadge = {
      Diproses: 'bg-amber-500/15 text-amber-600 dark:text-amber-300',
      Dikemas: 'bg-sky-500/15 text-sky-600 dark:text-sky-300',
      Dikirim: 'bg-purple-500/15 text-purple-600 dark:text-purple-300',
      Selesai: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
    };
    document.getElementById('my-orders-list').innerHTML = storeCache.my_orders.length
      ? storeCache.my_orders.map(o => `
        <div class="p-3.5 rounded-2xl surface-inner flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div class="flex items-center gap-2">
              <span class="font-extrabold text-teal-700 dark:text-toskaBright">${esc(o.order_code || '#' + o.id)}</span>
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${statusBadge[o.status] || statusBadge.Diproses}">${esc(o.status)}</span>
            </div>
            <p class="font-bold mt-1">${o.qty}× ${esc(o.product_name)}</p>
            <p class="text-[10px] text-slate-400">${esc(o.payment_method)} • ${esc(o.shipping_method)} • ${esc(o.created_at)}</p>
          </div>
          <div class="text-left sm:text-right">
            <p class="font-extrabold text-sm">${rupiah(o.total_price)}</p>
            ${o.discount_amount ? `<p class="text-[10px] text-emerald-500">Hemat ${rupiah(o.discount_amount)}</p>` : ''}
          </div>
        </div>
      `).join('')
      : '<p class="text-slate-400">Belum ada pesanan. Yuk mulai belanja minuman kalsium atau suplemen!</p>';

    lucide.createIcons();
  }

  window.setStoreFilter = (c) => { storeFilter = c; renderStore(); };
  window.toggleWishlistFilter = () => {
    onlyWishlist = !onlyWishlist;
    document.getElementById('mp-wish-btn').classList.toggle('border-rose-500', onlyWishlist);
    renderStore();
  };
  window.toggleWishlist = (pid) => {
    if (wishlist.includes(pid)) wishlist = wishlist.filter(x => x !== pid);
    else wishlist.push(pid);
    localStorage.setItem('kinetix_wishlist', JSON.stringify(wishlist));
    renderStore();
  };
  window.copyVoucher = (code) => {
    appliedVoucher = code;
    const inp = document.getElementById('cart-voucher');
    if (inp) inp.value = code;
    showToast(`Voucher ${code} diterapkan! Buka Keranjang untuk checkout.`);
    window.renderCart();
  };

  // Detail Produk & Ulasan Pembeli
  window.openProdDetail = async (pid) => {
    const p = storeCache.products.find(x => x.id === pid);
    if (!p) return;
    activeDetailProd = p;
    detailQty = 1;
    const discPct = p.original_price > p.price ? Math.round((1 - p.price / p.original_price) * 100) : 0;

    document.getElementById('prod-detail-body').innerHTML = `
      <div class="grid grid-cols-1 sm:grid-cols-12 gap-5">
        <div class="sm:col-span-5 rounded-2xl overflow-hidden bg-[#06131A] aspect-square relative">
          ${p.image_url ? `<img src="${esc(p.image_url)}" class="w-full h-full object-cover" onerror="this.style.display='none'" />` : ''}
          ${discPct > 0 ? `<span class="absolute top-3 left-3 px-2.5 py-1 rounded-xl bg-coral text-white text-xs font-extrabold">Hemat ${discPct}%</span>` : ''}
        </div>
        <div class="sm:col-span-7 flex flex-col justify-between">
          <div>
            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-toska/15 text-teal-700 dark:text-toskaBright">${esc(p.category)}</span>
            <h3 class="text-xl font-extrabold mt-2">${esc(p.name)}</h3>
            <div class="flex items-center gap-2 text-xs text-slate-500 mt-1">
              <span class="font-bold text-amber-500">★ ${(p.rating || 4.8).toFixed(1)}</span>
              <span>•</span><span>Terjual ${p.sold_count || 0}+</span>
              <span>•</span><span>Stok ${p.stock}</span>
            </div>
            <div class="mt-3 flex items-baseline gap-2.5">
              <span class="text-2xl font-extrabold toska-text">${rupiah(p.price)}</span>
              ${discPct > 0 ? `<span class="text-xs line-through text-slate-400">${rupiah(p.original_price)}</span>` : ''}
            </div>
            <p class="text-xs text-slate-600 dark:text-slate-300 mt-3 leading-relaxed">${esc(p.benefit)}</p>
            ${p.volume_ml ? `<p class="text-[11px] text-teal-700 dark:text-toskaBright font-semibold mt-2">💧 Bonus otomatis +${p.volume_ml}ml progres hidrasi per botol</p>` : ''}
          </div>

          <div class="mt-5 space-y-3">
            <div class="flex items-center gap-3">
              <span class="text-xs font-semibold text-slate-500">Jumlah:</span>
              <div class="inline-flex items-center rounded-xl surface-inner p-1">
                <button type="button" onclick="window.chgDetailQty(-1)" class="w-7 h-7 rounded-lg hover:bg-toska/15 font-bold">-</button>
                <span id="det-qty" class="px-3 text-xs font-extrabold">1</span>
                <button type="button" onclick="window.chgDetailQty(1)" class="w-7 h-7 rounded-lg hover:bg-toska/15 font-bold">+</button>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2.5">
              <button type="button" onclick="window.addToCart(${p.id}, detailQty); window.closeProdDetail();" class="py-2.5 rounded-xl surface-inner hover:border-toska text-xs font-bold">+ Keranjang</button>
              <button type="button" onclick="window.addToCart(${p.id}, detailQty); window.closeProdDetail(); window.toggleCartDrawer(true);" class="py-2.5 rounded-xl btn-gradient text-white text-xs font-bold shadow-lg">Beli Langsung</button>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-5 border-t border-toska/15">
        <h4 class="font-bold text-sm mb-3">Ulasan Pembeli</h4>
        <form id="review-form" class="flex flex-col sm:flex-row gap-2 mb-4">
          <select id="rev-rating" class="field-input px-3 py-2 rounded-xl text-xs font-bold">
            <option value="5">★★★★★ (5)</option><option value="4">★★★★ (4)</option><option value="3">★★★ (3)</option>
          </select>
          <input id="rev-comment" type="text" required placeholder="Tulis pengalamanmu tentang produk ini..." class="field-input flex-1 px-3 py-2 rounded-xl text-xs" />
          <button type="submit" class="px-4 py-2 rounded-xl bg-toska text-white text-xs font-bold">Kirim</button>
        </form>
        <div id="prod-reviews-list" class="space-y-2 text-xs max-h-40 overflow-y-auto"></div>
      </div>
    `;

    document.getElementById('prod-detail-modal').classList.remove('hidden');
    document.getElementById('review-form').onsubmit = async (e) => {
      e.preventDefault();
      const res = await fetch(`/api/store/products/${p.id}/reviews`, {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating: Number(document.getElementById('rev-rating').value), comment: document.getElementById('rev-comment').value })
      });
      if (res.ok) {
        document.getElementById('rev-comment').value = '';
        renderReviews((await res.json()).reviews);
        loadStore();
        showToast('Terima kasih atas ulasanmu!');
      }
    };

    const rRes = await fetch(`/api/store/products/${p.id}/reviews`, { credentials: 'same-origin' });
    if (rRes.ok) renderReviews((await rRes.json()).reviews);
    lucide.createIcons();
  };

  function renderReviews(revs) {
    document.getElementById('prod-reviews-list').innerHTML = revs.length
      ? revs.map(r => `<div class="p-2.5 rounded-xl surface-inner"><div class="flex justify-between"><span class="font-bold">${esc(r.reviewer_name)}</span><span class="text-amber-500 font-bold">${'★'.repeat(r.rating)}</span></div><p class="text-slate-600 dark:text-slate-300 mt-1">${esc(r.comment)}</p></div>`).join('')
      : '<p class="text-slate-400">Belum ada ulasan. Jadilah yang pertama mengulas!</p>';
  }

  window.chgDetailQty = (d) => {
    if (!activeDetailProd) return;
    detailQty = Math.max(1, Math.min(activeDetailProd.stock, detailQty + d));
    document.getElementById('det-qty').textContent = detailQty;
  };
  window.closeProdDetail = () => document.getElementById('prod-detail-modal').classList.add('hidden');

  // Keranjang Belanja & Checkout
  function saveCart() {
    localStorage.setItem('kinetix_cart', JSON.stringify(cart));
    updateCartBadge();
    window.renderCart();
  }
  function updateCartBadge() {
    const el = document.getElementById('store-cart-count');
    if (el) el.textContent = cart.reduce((a, b) => a + b.qty, 0);
  }
  window.addToCart = (pid, qty = 1) => {
    const prod = storeCache.products.find(x => x.id === pid);
    if (!prod || prod.stock < 1) return;
    const found = cart.find(x => x.product_id === pid);
    if (found) found.qty = Math.min(prod.stock, found.qty + qty);
    else cart.push({ product_id: pid, qty });
    saveCart();
    showToast(`${prod.name} masuk keranjang!`);
  };
  window.chgCartQty = (pid, delta) => {
    const item = cart.find(x => x.product_id === pid);
    if (!item) return;
    item.qty += delta;
    if (item.qty <= 0) cart = cart.filter(x => x.product_id !== pid);
    saveCart();
  };
  window.toggleCartDrawer = (open) => {
    document.getElementById('cart-backdrop').classList.toggle('hidden', !open);
    document.getElementById('cart-drawer').classList.toggle('translate-x-full', !open);
    if (open) window.renderCart();
  };
  window.applyCartVoucher = () => {
    appliedVoucher = document.getElementById('cart-voucher').value.trim().toUpperCase();
    if (appliedVoucher && !['FIT10', 'KALSIUM10'].includes(appliedVoucher)) {
      appliedVoucher = '';
      showToast('Kode voucher tidak valid. Coba FIT10 atau KALSIUM10.');
    } else if (appliedVoucher) {
      showToast(`Voucher ${appliedVoucher} aktif!`);
    }
    window.renderCart();
  };

  window.renderCart = () => {
    const box = document.getElementById('cart-items-box');
    if (!box) return;
    let sub = 0;
    const rows = cart.map(it => {
      const p = storeCache.products.find(x => x.id === it.product_id);
      if (!p) return '';
      sub += p.price * it.qty;
      return `
        <div class="p-3 rounded-2xl surface-inner flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl overflow-hidden bg-[#06131A] shrink-0">
            ${p.image_url ? `<img src="${esc(p.image_url)}" class="w-full h-full object-cover" />` : ''}
          </div>
          <div class="flex-1 min-w-0">
            <p class="font-bold truncate">${esc(p.name)}</p>
            <p class="text-[11px] font-extrabold toska-text">${rupiah(p.price)}</p>
          </div>
          <div class="flex items-center gap-1.5">
            <button type="button" onclick="window.chgCartQty(${p.id}, -1)" class="w-6 h-6 rounded-lg glass font-bold">-</button>
            <span class="font-extrabold w-5 text-center">${it.qty}</span>
            <button type="button" onclick="window.chgCartQty(${p.id}, 1)" class="w-6 h-6 rounded-lg glass font-bold">+</button>
          </div>
        </div>
      `;
    }).join('');

    box.innerHTML = rows || '<p class="text-center text-slate-400 py-14">Keranjang masih kosong.<br>Tambahkan minuman kalsium atau suplemen dulu!</p>';

    const shipMethod = document.getElementById('cart-shipping')?.value || 'Reguler';
    const shipFee = cart.length ? (shipMethod === 'Express' ? 15000 : (shipMethod === 'Reguler' ? 8000 : 0)) : 0;
    let disc = 0;
    if (appliedVoucher === 'FIT10') disc = Math.round(sub * 0.10);
    else if (appliedVoucher === 'KALSIUM10' && sub >= 30000) disc = 10000;

    document.getElementById('cart-sub').textContent = rupiah(sub);
    document.getElementById('cart-ship').textContent = rupiah(shipFee);
    document.getElementById('cart-disc').textContent = '-' + rupiah(disc);
    document.getElementById('cart-total').textContent = rupiah(Math.max(0, sub - disc + shipFee));
  };

  window.submitCheckout = async () => {
    if (!cart.length) return showToast('Keranjang masih kosong!');
    const res = await fetch('/api/store/checkout', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: cart,
        voucher: appliedVoucher,
        shipping_method: document.getElementById('cart-shipping').value,
        payment_method: document.getElementById('cart-payment').value,
        shipping_address: document.getElementById('cart-address').value
      })
    });
    const d = await res.json();
    if (!res.ok) return showToast(d.error || 'Checkout gagal.');
    cart = [];
    appliedVoucher = '';
    saveCart();
    window.toggleCartDrawer(false);
    showToast(d.hydration_added ? `Order ${d.order_code} sukses! +${d.hydration_added}ml hidrasi ditambahkan.` : `Order ${d.order_code} berhasil!`);
    loadStore();
    loadDashboard();
  };

  // ============ 4. DEVELOPER SELLER CENTER (HANYA MOUNT JIKA role === 'developer') ============
  function mountDeveloperUI() {
    if (devMounted) return;
    devMounted = true;
    const main = document.querySelector('main');
    const nav = document.querySelector('nav.anim-dock');
    if (!main || !nav) return;

    nav.classList.remove('grid-cols-6');
    nav.classList.add('grid-cols-7');

    const devBtn = document.createElement('button');
    devBtn.type = 'button';
    devBtn.id = 'dock-dev-btn';
    devBtn.dataset.tab = 'dev';
    devBtn.className = 'dock-item py-2.5 px-2 rounded-2xl flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-toska/10';
    devBtn.innerHTML = '<i data-lucide="shield-check" class="w-4 h-4 shrink-0"></i><span>Dev</span>';
    devBtn.onclick = () => switchTab('dev');
    nav.appendChild(devBtn);

    const devSec = document.createElement('section');
    devSec.id = 'tab-dev';
    devSec.className = 'tab-panel hidden space-y-6';
    devSec.innerHTML = `
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4" id="dev-kpi-grid"></div>
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div class="lg:col-span-5 glass rounded-3xl p-6">
          <h3 class="text-lg font-extrabold mb-1 flex items-center gap-2">
            <i data-lucide="package-plus" class="w-5 h-5 text-toska"></i> Seller Center: Tambah Produk
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">Unggah foto produk, atur diskon & langsung tampil di Marketplace.</p>
          <form id="dev-product-form" class="space-y-3">
            <div><label class="text-xs text-slate-500">Nama Produk</label><input id="dp-name" required placeholder="Contoh: CalciBoost Sport 500ml" class="field-input w-full mt-1 px-3.5 py-2 rounded-xl text-sm" /></div>
            <div class="grid grid-cols-2 gap-3">
              <div><label class="text-xs text-slate-500">Kategori</label><select id="dp-cat" class="field-input w-full mt-1 px-3 py-2 rounded-xl text-sm"><option>Minuman Kalsium</option><option>Minuman Isotonik</option><option>Suplemen Protein</option><option>Energy Drink</option><option>Aksesoris Olahraga</option></select></div>
              <div><label class="text-xs text-slate-500">Badge Promo</label><input id="dp-badge" value="Top Kalsium" class="field-input w-full mt-1 px-3 py-2 rounded-xl text-sm" /></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div><label class="text-xs text-slate-500">Harga Jual (Rp)</label><input id="dp-price" type="number" min="1000" value="28000" required class="field-input w-full mt-1 px-3 py-2 rounded-xl text-sm" /></div>
              <div><label class="text-xs text-slate-500">Harga Coret / Asli (Rp)</label><input id="dp-orig" type="number" min="0" value="35000" class="field-input w-full mt-1 px-3 py-2 rounded-xl text-sm" /></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div><label class="text-xs text-slate-500">Stok</label><input id="dp-stock" type="number" min="1" value="30" required class="field-input w-full mt-1 px-3 py-2 rounded-xl text-sm" /></div>
              <div><label class="text-xs text-slate-500">Volume (ml)</label><input id="dp-vol" type="number" min="0" value="500" class="field-input w-full mt-1 px-3 py-2 rounded-xl text-sm" /></div>
            </div>
            <div><label class="text-xs text-slate-500">Foto Produk (Upload File atau URL)</label><input id="dp-file" type="file" accept=".png,.jpg,.jpeg,.webp" class="field-input w-full mt-1 px-2.5 py-1.5 rounded-xl text-xs" /></div>
            <div><label class="text-xs text-slate-500">Manfaat Produk</label><textarea id="dp-benefit" rows="2" placeholder="Tinggi kalsium untuk tulang kuat & pemulihan otot..." class="field-input w-full mt-1 px-3.5 py-2 rounded-xl text-sm"></textarea></div>
            <button type="submit" class="w-full btn-gradient text-white font-bold py-2.5 rounded-xl text-xs shadow-lg">Publikasikan ke Marketplace</button>
          </form>
        </div>

        <div class="lg:col-span-7 glass rounded-3xl p-6 flex flex-col">
          <h3 class="text-lg font-extrabold mb-1 flex items-center gap-2"><i data-lucide="headphones" class="w-5 h-5 text-ocean dark:text-sky-400"></i> Kotak Masuk Live CS</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">Balas pertanyaan customer secara langsung.</p>
          <div class="grid grid-cols-1 sm:grid-cols-12 gap-3 flex-1 min-h-[300px]">
            <div id="dev-cs-threads" class="sm:col-span-4 surface-inner rounded-2xl p-2 space-y-1.5 max-h-80 overflow-y-auto"></div>
            <div class="sm:col-span-8 surface-inner rounded-2xl p-3 flex flex-col justify-between">
              <div id="dev-cs-messages" class="space-y-2 max-h-60 overflow-y-auto pr-1 text-xs"><p class="text-slate-400 text-center py-10">Pilih percakapan user di samping.</p></div>
              <form id="dev-cs-reply-form" class="flex gap-2 mt-3 pt-2 border-t border-teal-500/15">
                <input id="dev-cs-input" type="text" placeholder="Tulis balasan Customer Service..." class="field-input flex-1 px-3 py-2 rounded-xl text-xs" />
                <button type="submit" class="btn-gradient text-white px-4 py-2 rounded-xl text-xs font-bold">Kirim</button>
              </form>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div class="lg:col-span-5 glass rounded-3xl p-6"><h3 class="font-bold text-base mb-3">Kelola Katalog Produk</h3><div id="dev-products-list" class="space-y-2.5 max-h-80 overflow-y-auto text-xs"></div></div>
        <div class="lg:col-span-7 glass rounded-3xl p-6"><h3 class="font-bold text-base mb-3">Kelola Pesanan & Status Pengiriman</h3><div id="dev-orders-list" class="space-y-2.5 max-h-80 overflow-y-auto text-xs"></div></div>
      </div>

      <div class="glass rounded-3xl p-6">
        <h3 class="font-bold text-base mb-3 flex items-center gap-2"><i data-lucide="users" class="w-4 h-4 text-toska"></i> Data Seluruh User Terdaftar</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead><tr class="text-slate-500 border-b border-teal-500/20"><th class="py-2">User</th><th class="py-2">Role</th><th class="py-2">BB / TB</th><th class="py-2">Goal</th><th class="py-2">Latihan</th><th class="py-2">Total Volume</th><th class="py-2 text-right">Total Belanja</th></tr></thead>
            <tbody id="dev-users-tbody" class="divide-y divide-teal-500/10"></tbody>
          </table>
        </div>
      </div>
    `;
    main.appendChild(devSec);

    document.getElementById('dev-product-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData();
      fd.append('name', document.getElementById('dp-name').value);
      fd.append('category', document.getElementById('dp-cat').value);
      fd.append('badge', document.getElementById('dp-badge').value);
      fd.append('price', document.getElementById('dp-price').value);
      fd.append('original_price', document.getElementById('dp-orig').value);
      fd.append('stock', document.getElementById('dp-stock').value);
      fd.append('volume_ml', document.getElementById('dp-vol').value);
      fd.append('benefit', document.getElementById('dp-benefit').value);
      const fileInp = document.getElementById('dp-file');
      if (fileInp.files[0]) fd.append('image_file', fileInp.files[0]);

      const res = await fetch('/api/dev/products', { method: 'POST', credentials: 'same-origin', body: fd });
      if (!res.ok) return showToast('Gagal menambah produk.');
      document.getElementById('dp-name').value = ''; document.getElementById('dp-benefit').value = ''; fileInp.value = '';
      showToast('Produk dipublikasikan ke Marketplace & notifikasi terkirim!');
      loadDevOverview();
    });

    document.getElementById('dev-cs-reply-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!devSelectedUid) return showToast('Pilih user terlebih dahulu.');
      const inp = document.getElementById('dev-cs-input');
      const txt = inp.value.trim();
      if (!txt) return;
      inp.value = '';
      const res = await fetch(`/api/dev/chat/${devSelectedUid}`, {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: txt })
      });
      const data = await res.json();
      if (res.ok) { renderDevChatMessages(data.messages); showToast('Balasan CS terkirim!'); }
    });
    lucide.createIcons();
  }

  // ============ 5. NOTIFIKASI, HOOKS & CHAT ============
  window.renderNotifications = function (list) {
    const unread = (typeof appData !== 'undefined' && appData) ? (appData.unread_count || 0) : list.filter(x => !x.is_read).length;
    const dot = document.getElementById('notif-dot');
    if (dot) {
      if (unread > 0) {
        dot.className = 'min-w-[18px] h-[18px] px-1 rounded-full bg-coral text-white text-[10px] font-extrabold flex items-center justify-center ring-2 ring-white dark:ring-abyss absolute -top-1.5 -right-1.5';
        dot.textContent = unread > 9 ? '9+' : String(unread);
      } else { dot.classList.add('hidden'); }
    }
    const toneMap = { toska: 'text-toska bg-toska/15', cyan: 'text-toska bg-toska/15', ocean: 'text-sky-600 dark:text-sky-400 bg-ocean/15', rose: 'text-rose-500 bg-rose-500/15', amber: 'text-coral bg-coral/15', emerald: 'text-emerald-500 bg-emerald-500/15' };
    const panel = document.getElementById('notif-list');
    if (!panel) return;
    const headBtn = unread > 0 ? `<button type="button" onclick="window.markAllNotifsRead()" class="w-full mb-2 py-1.5 rounded-xl bg-toska/15 text-teal-700 dark:text-toskaBright text-[11px] font-bold hover:bg-toska hover:text-white transition">Tandai Semua Dibaca (${unread})</button>` : '';
    panel.innerHTML = headBtn + (list.length ? list.map(n => `
      <div class="p-3 rounded-xl surface-inner flex items-start gap-3 ${n.is_read ? 'opacity-75' : 'border-toska/40'}">
        <div class="p-2 rounded-lg shrink-0 ${toneMap[n.tone] || toneMap.toska}"><i data-lucide="${esc(n.icon || 'bell')}" class="w-4 h-4"></i></div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2"><p class="text-xs font-bold truncate">${esc(n.title)}</p>${n.is_read ? '' : '<span class="w-2 h-2 rounded-full bg-coral shrink-0"></span>'}</div>
          <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 leading-snug">${esc(n.body)}</p>
          <p class="text-[9px] text-slate-400 mt-1">${esc(n.created_at || '')}</p>
        </div>
      </div>
    `).join('') : '<p class="text-xs text-slate-400 text-center py-4">Belum ada pemberitahuan.</p>');
    panel.classList.add('max-h-80', 'overflow-y-auto', 'pr-1');
    lucide.createIcons();
  };

  window.markAllNotifsRead = async function () {
    await fetch('/api/notifications/read', { method: 'POST', credentials: 'same-origin' });
    loadDashboard();
  };

  const origSwitchTab = window.switchTab;
  window.switchTab = function (tab) {
    const isDev = (typeof appData !== 'undefined' && appData && appData.profile && appData.profile.role === 'developer');
    if (tab === 'dev' && !isDev) { origSwitchTab('lab'); return; }
    origSwitchTab(tab);
    if (tab === 'store') loadStore();
    if (tab === 'dev' && isDev) loadDevOverview();
  };

  const origLoadDashboard = window.loadDashboard;
  window.loadDashboard = async function () {
    await origLoadDashboard();
    if (typeof appData !== 'undefined' && appData && appData.profile) {
      const isDev = appData.profile.role === 'developer';
      if (isDev) {
        mountDeveloperUI();
        const goalEl = document.getElementById('drawer-goal');
        if (goalEl) goalEl.textContent = 'ROLE: DEVELOPER';
      } else if (!appData.profile.onboarding_done && !onboardingShownOnce) {
        onboardingShownOnce = true;
        setTimeout(() => startGuidedTour(0), 650);
      }
    }
  };

  function toggleChat(open) {
    chatOpen = open;
    document.getElementById('chat-window').classList.toggle('hidden', !open);
    document.getElementById('chat-fab').classList.toggle('hidden', open);
    clearInterval(chatPollTimer);
    if (open) { fetchChatHistory(); chatPollTimer = setInterval(fetchChatHistory, 6000); }
  }
  function setChatMode(m) {
    chatMode = m;
    document.getElementById('cm-bot').className = m === 'bot' ? 'flex-1 py-1.5 rounded-xl text-[11px] font-bold bg-toska text-white' : 'flex-1 py-1.5 rounded-xl text-[11px] font-semibold text-slate-600 dark:text-slate-300';
    document.getElementById('cm-cs').className = m === 'cs' ? 'flex-1 py-1.5 rounded-xl text-[11px] font-bold bg-ocean text-white' : 'flex-1 py-1.5 rounded-xl text-[11px] font-semibold text-slate-600 dark:text-slate-300';
    document.getElementById('chat-input').placeholder = m === 'cs' ? 'Tulis pesan ke Customer Service...' : 'Tanya AI Coach Bot...';
  }
  async function fetchChatHistory() {
    const res = await fetch('/api/chat', { credentials: 'same-origin' });
    if (res.ok) renderChatMessages((await res.json()).messages);
  }
  async function sendChat(text) {
    const res = await fetch('/api/chat', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text, mode: chatMode }) });
    if (!res.ok) return;
    renderChatMessages((await res.json()).messages);
    if (chatMode === 'cs') showToast('Pesan terkirim ke Customer Service!');
  }
  function renderChatMessages(msgs) {
    const box = document.getElementById('chat-messages');
    const welcome = `<div class="p-3 rounded-2xl surface-inner max-w-[88%]"><p class="text-[10px] font-bold text-toska mb-0.5">KINETIX AI Coach</p><p class="leading-relaxed">Halo! Tanya saya soal otot yang siap dilatih, target kalori, voucher minuman kalsium, atau pilih tab <b>Live CS</b>.</p></div>`;
    box.innerHTML = welcome + msgs.map(m => {
      const isUser = m.sender_role === 'user';
      const label = m.sender_role === 'developer' ? 'Customer Service' : 'KINETIX AI Coach';
      return `<div class="flex ${isUser ? 'justify-end' : 'justify-start'}"><div class="max-w-[85%] p-3 rounded-2xl ${isUser ? 'btn-gradient text-white' : (m.sender_role === 'developer' ? 'bg-ocean/15 border border-ocean/35' : 'surface-inner')}">${isUser ? '' : `<p class="text-[10px] font-bold ${m.sender_role === 'developer' ? 'text-sky-600 dark:text-sky-400' : 'text-toska'} mb-0.5">${label}</p>`}<p class="whitespace-pre-line leading-relaxed">${esc(m.message)}</p><p class="text-[9px] opacity-70 mt-1 text-right">${esc(m.created_at.slice(11))}</p></div></div>`;
    }).join('');
    box.scrollTop = box.scrollHeight;
  }

  async function loadDevOverview() {
    const res = await fetch('/api/dev/overview', { credentials: 'same-origin' });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById('dev-kpi-grid').innerHTML = [
      { l: 'Total User', v: d.stats.total_users, c: 'text-toska' },
      { l: 'Produk Marketplace', v: d.stats.total_products, c: 'text-sky-500' },
      { l: 'Total Pesanan', v: d.stats.total_orders, c: 'text-coral' },
      { l: 'Omzet Marketplace', v: rupiah(d.stats.total_revenue), c: 'text-emerald-500' }
    ].map(k => `<div class="glass rounded-2xl p-4"><p class="text-xs text-slate-500">${k.l}</p><p class="text-2xl font-extrabold mt-1 ${k.c}">${k.v}</p></div>`).join('');

    document.getElementById('dev-users-tbody').innerHTML = d.users.map(u => `
      <tr class="hover:bg-toska/5">
        <td class="py-2.5"><p class="font-bold">${esc(u.name)}</p><p class="text-[10px] text-slate-400">@${esc(u.username)} • ${esc(u.email)}</p></td>
        <td class="py-2.5"><span class="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${u.role === 'developer' ? 'bg-ocean/20 text-sky-500' : 'bg-toska/15 text-toska'}">${esc(u.role)}</span></td>
        <td class="py-2.5">${u.weight_kg} kg / ${u.height_cm} cm</td>
        <td class="py-2.5 uppercase font-semibold">${esc(u.goal)}</td>
        <td class="py-2.5 font-bold">${u.workout_count} sesi</td>
        <td class="py-2.5 font-bold">${Number(u.total_volume).toLocaleString('id-ID')} kg</td>
        <td class="py-2.5 text-right font-bold text-teal-600 dark:text-toskaBright">${rupiah(u.total_spent)}</td>
      </tr>
    `).join('');

    document.getElementById('dev-products-list').innerHTML = d.products.map(p => `
      <div class="p-3 rounded-xl surface-inner flex items-center justify-between gap-2">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="w-10 h-10 rounded-lg overflow-hidden bg-[#06131A] shrink-0">${p.image_url ? `<img src="${esc(p.image_url)}" class="w-full h-full object-cover"/>` : ''}</div>
          <div class="min-w-0"><p class="font-bold truncate">${esc(p.name)}</p><p class="text-[10px] text-slate-400">${rupiah(p.price)} • Stok: <b>${p.stock}</b> • Terjual ${p.sold_count || 0}</p></div>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <button type="button" onclick="window.devUpdateStock(${p.id}, 10)" class="px-2 py-1 rounded-lg bg-toska/15 text-teal-700 dark:text-toskaBright font-bold">+10</button>
          <button type="button" onclick="window.devDeleteProduct(${p.id})" class="px-2 py-1 rounded-lg bg-rose-500/15 text-rose-500 font-bold">Hapus</button>
        </div>
      </div>
    `).join('');

    document.getElementById('dev-orders-list').innerHTML = d.orders.length ? d.orders.map(o => `
      <div class="p-3 rounded-xl surface-inner flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <p class="font-bold">${esc(o.order_code || '#' + o.id)} — ${esc(o.buyer_name)}</p>
          <p class="text-[11px]">${o.qty}× ${esc(o.product_name)} • <b>${rupiah(o.total_price)}</b></p>
          <p class="text-[10px] text-slate-400">${esc(o.payment_method)} • ${esc(o.shipping_method)} • ${esc(o.shipping_address || '-')}</p>
        </div>
        <select onchange="window.devUpdateOrderStatus(${o.id}, this.value)" class="field-input px-2.5 py-1.5 rounded-xl text-xs font-bold shrink-0">
          ${['Diproses', 'Dikemas', 'Dikirim', 'Selesai'].map(st => `<option value="${st}" ${o.status === st ? 'selected' : ''}>${st}</option>`).join('')}
        </select>
      </div>
    `).join('') : '<p class="text-slate-400">Belum ada pesanan masuk.</p>';

    document.getElementById('dev-cs-threads').innerHTML = d.threads.length ? d.threads.map(t => `<button type="button" onclick="window.devOpenThread(${t.user_id})" class="w-full text-left p-2.5 rounded-xl ${devSelectedUid === t.user_id ? 'bg-toska text-white' : 'glass hover:border-toska'}"><p class="text-xs font-bold truncate">${esc(t.name)}</p><p class="text-[10px] opacity-80 truncate">${esc(t.last_message || '')}</p></button>`).join('') : '<p class="text-xs text-slate-400 p-3 text-center">Belum ada chat CS masuk.</p>';
    if (d.threads.length && !devSelectedUid) window.devOpenThread(d.threads[0].user_id);
  }

  window.devUpdateStock = async (pid, delta) => { await fetch(`/api/dev/products/${pid}`, { method: 'PATCH', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stock_delta: delta }) }); showToast(`Stok ditambah +${delta}.`); loadDevOverview(); };
  window.devDeleteProduct = async (pid) => { await fetch(`/api/dev/products/${pid}`, { method: 'DELETE', credentials: 'same-origin' }); showToast('Produk dihapus.'); loadDevOverview(); };
  window.devUpdateOrderStatus = async (oid, status) => {
    const res = await fetch(`/api/dev/orders/${oid}`, { method: 'PATCH', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) });
    if (res.ok) showToast(`Status pesanan diubah ke "${status}" & notifikasi dikirim ke pembeli!`);
  };
  window.devOpenThread = async (uid) => { devSelectedUid = uid; const res = await fetch(`/api/dev/chat/${uid}`, { credentials: 'same-origin' }); if (res.ok) renderDevChatMessages((await res.json()).messages); };

  function renderDevChatMessages(msgs) {
    const box = document.getElementById('dev-cs-messages');
    box.innerHTML = msgs.map(m => `<div class="flex ${m.sender_role === 'developer' ? 'justify-end' : 'justify-start'}"><div class="max-w-[85%] p-2.5 rounded-xl ${m.sender_role === 'developer' ? 'btn-gradient text-white' : 'glass'}"><p class="text-[9px] font-bold uppercase opacity-75">${esc(m.sender_role)}</p><p class="whitespace-pre-line">${esc(m.message)}</p></div></div>`).join('');
    box.scrollTop = box.scrollHeight;
  }

  document.addEventListener('DOMContentLoaded', mountUserUI);
})();