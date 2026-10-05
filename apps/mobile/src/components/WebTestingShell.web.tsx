/**
 * ****************************************
 * For Usability Testing or UAT only.
 * Web testing page; excluded from native UI.
 * ****************************************
 */
import { useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { WEB_APP_ENVIRONMENT, WEB_APP_VERSION } from '../config/webTestingRelease';
import './WebTestingShell.css';

const features = [
  { title: 'Check prices', text: 'Choose your location, search for a food, and compare nearby store prices.' },
  { title: 'Plan your week', text: 'Tell us who you shop for and what you like to eat. Then explore your weekly plan.' },
  { title: 'Manage your pantry', text: 'See your foods in What you have. Mark shopping items as purchased to add them to your pantry.' },
  { title: 'Find meal ideas', text: 'Browse recipes recommended for your pantry. Open a recipe to see which ingredients you have and which you still need.' },
  { title: 'Check recipe ingredients', text: 'Use Check what I have in a recipe and mark ingredients you already have. You can add them without entering an amount.' },
  { title: 'Scan grocery receipts', text: 'Upload a receipt to find food items and add them to your pantry after checking the results.' },
];

export function WebTestingShell() {
  const [restart, setRestart] = useState(0);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [receiptHelp, setReceiptHelp] = useState({ hovered: false, focused: false, pinned: false });
  const showReceiptHelp = receiptHelp.hovered || receiptHelp.focused || receiptHelp.pinned;
  useEffect(() => {
    if (!resetting) return;
    // Effects run after the preview has unmounted, stopping its pending work.
    const reset = async () => {
    try {
      // Unmount the preview while clearing local data, so it cannot reuse tokens.
      const keys = await AsyncStorage.getAllKeys();
      await AsyncStorage.multiRemove(keys.filter((key) => key.startsWith('wisebasket.')));
      for (const key of Object.keys(window.sessionStorage)) {
        if (key.startsWith('wisebasket.')) window.sessionStorage.removeItem(key);
      }
      setRestart((value) => value + 1);
    } catch {
      setResetError('Could not reset the app. Please try again.');
    } finally {
      setResetting(false);
    }
    };
    void reset();
  }, [resetting]);
  const url = new URL(window.location.href);
  url.searchParams.set('embedded', '1');
  const resetApp = () => {
    setResetError(null);
    setResetting(true);
  };

  return (
    <main className="wb-testing">
      <header>
        <div className="wb-title">
          <h1>Try WiseBasket</h1>
          <div className="wb-mobile-release" aria-label="WiseBasket app version and environment">
            <span>WiseBasket v{WEB_APP_VERSION}</span>
            <span className="wb-environment">{WEB_APP_ENVIRONMENT}</span>
          </div>
        </div>
        <p>Explore the app below, then tell us what you think.</p>
        <button className="wb-mobile-reset" disabled={resetting} onClick={resetApp}
          aria-label="Reset app and sign out">{resetting ? 'Resetting…' : 'Reset'}</button>
        <a className="wb-mobile-feedback" href="https://forms.gle/JNANEXhvpYWR7UDS8"
          target="_blank" rel="noopener noreferrer" aria-label="Share feedback">Share ↗</a>
      </header>
      {resetError && <p className="wb-mobile-error" role="alert">{resetError}</p>}
      <div className="wb-testing-layout">
        <section aria-labelledby="wb-features-title">
          <h2 className="wb-nav-title" id="wb-features-title">What you can do</h2>
          <ul className="wb-feature-list">
            {features.map((item) => (
              item.title === 'Scan grocery receipts' ? (
                <li key={item.title} className="wb-receipt-feature"
                  onMouseEnter={() => setReceiptHelp((value) => ({ ...value, hovered: true }))}
                  onMouseLeave={() => setReceiptHelp((value) => ({ ...value, hovered: false }))}
                >
                  <h3><button className="wb-receipt-trigger"
                    aria-expanded={showReceiptHelp} aria-controls="wb-receipt-help"
                    onFocus={() => setReceiptHelp((value) => ({ ...value, focused: true }))}
                    onBlur={() => setReceiptHelp((value) => ({ ...value, focused: false }))}
                    onClick={() => setReceiptHelp((value) => ({ ...value, pinned: !value.pinned }))}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') setReceiptHelp({ hovered: false, focused: false, pinned: false });
                    }}
                  >{item.title}<span className="wb-receipt-indicator" aria-hidden="true">
                    {showReceiptHelp ? '−' : '+'}
                  </span></button></h3>
                  <small className="wb-receipt-hint">Hover or click for steps</small>
                  <p>{item.text}</p>
                  <section id="wb-receipt-help" hidden={!showReceiptHelp}
                    className="wb-receipt-help" aria-labelledby="wb-receipt-help-title">
                    <h3 id="wb-receipt-help-title">How to scan a receipt</h3>
                    <ol>
                      <li>Open My Basket, then What you have. Choose Upload image.</li>
                      <li>Choose a clear photo of the whole receipt. Keep it flat and make sure the item names are readable.</li>
                      <li>Wait for Check what we found. Review each food and correct any wrong or unmatched items.</li>
                      <li>Press Confirm purchase to save the foods to your pantry.</li>
                    </ol>
                  </section>
                </li>
              ) : <li key={item.title}><h3>{item.title}</h3><p>{item.text}</p></li>
            ))}
          </ul>
        </section>
        <div className="wb-preview">
          <p className="wb-release" aria-label="App version and environment">
            <span>v{WEB_APP_VERSION}</span>
            <span className="wb-environment">{WEB_APP_ENVIRONMENT}</span>
          </p>
          <div className="wb-phone">
          {resetting ? <div className="wb-resetting" role="status">Resetting the app…</div>
            : <iframe key={restart} title="WiseBasket app preview" src={url.toString()} />}
          </div>
        </div>
        <aside className="wb-guide">
          <section className="wb-feedback" aria-labelledby="wb-feedback-title">
            <h2 id="wb-feedback-title">What do you think?</h2>
            <p>What worked well? What could be better? Share your experience to help us improve WiseBasket.</p>
            <a className="wb-feedback-link" href="https://forms.gle/JNANEXhvpYWR7UDS8"
              target="_blank" rel="noopener noreferrer">Share feedback <span aria-hidden="true">↗</span></a>
            <small>Opens the feedback form in a new tab. You can come back to the app anytime.</small>
          </section>
          <section className="wb-journey">
            <h2>Get started</h2>
            <p>Sign in or create an account, then explore the app.</p>
          </section>
          <button disabled={resetting} onClick={resetApp}>{resetting ? 'Resetting…' : 'Reset app'}</button>
          <small>Signs you out and clears this browser’s app data. You’ll need to sign in again. Your account data stays saved.</small>
          {resetError && <p role="alert">{resetError}</p>}
        </aside>
      </div>
    </main>
  );
}
