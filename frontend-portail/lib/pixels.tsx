/**
 * Pixels — helpers Meta Pixel + TikTok Pixel + Google Analytics.
 *
 * Utilisation :
 *   <PixelsHead />                     // à monter une fois dans layout.tsx ou page.tsx (Head)
 *   firePixel('Lead', { value: 380 }); // à appeler aux conversions clés
 *
 * Événements standards :
 *   - PageView       : vue de page (auto-fired par les scripts, on l'appelle explicitement pour SPA)
 *   - Lead           : prospect capturé (étape intermédiaire OU finale — selon ta stratégie de bidding)
 *   - CompleteRegistration : formulaire soumis avec succès
 *   - Contact        : appel téléphonique déclenché
 *
 * Config via variables d'env NEXT_PUBLIC_* (exposées au client — c'est normal pour un pixel) :
 *   NEXT_PUBLIC_META_PIXEL_ID
 *   NEXT_PUBLIC_TIKTOK_PIXEL_ID
 *   NEXT_PUBLIC_GA_MEASUREMENT_ID
 *
 * ⚠️ Pas de pixel = pas de retargeting = CPA multiplié par 2-3. À installer AVANT le premier ad.
 */
import Script from 'next/script';

const META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID;
const TIKTOK_PIXEL_ID = process.env.NEXT_PUBLIC_TIKTOK_PIXEL_ID;
const GA_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

declare global {
  interface Window {
    fbq?: (...args: any[]) => void;
    ttq?: any;
    gtag?: (...args: any[]) => void;
  }
}

export function PixelsHead() {
  return (
    <>
      {/* Meta (Facebook + Instagram) --------------------------------- */}
      {META_PIXEL_ID && (
        <>
          <Script
            id="meta-pixel"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
              __html: `
                !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){
                n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};
                if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
                n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;
                s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
                document,'script','https://connect.facebook.net/en_US/fbevents.js');
                fbq('init', '${META_PIXEL_ID}');
                fbq('track', 'PageView');
              `,
            }}
          />
          <noscript>
            <img
              height="1"
              width="1"
              style={{ display: 'none' }}
              alt=""
              src={`https://www.facebook.com/tr?id=${META_PIXEL_ID}&ev=PageView&noscript=1`}
            />
          </noscript>
        </>
      )}

      {/* TikTok Pixel ------------------------------------------------ */}
      {TIKTOK_PIXEL_ID && (
        <Script
          id="tiktok-pixel"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              !function (w, d, t) {
                w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];
                ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"];
                ttq.setAndDefer=function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};
                for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);
                ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e};
                ttq.load=function(e,n){var i="https://analytics.tiktok.com/i18n/pixel/events.js";
                ttq._i=ttq._i||{},ttq._i[e]=[],ttq._i[e]._u=i,ttq._t=ttq._t||{},ttq._t[e]=+new Date,ttq._o=ttq._o||{},ttq._o[e]=n||{};
                var o=document.createElement("script");o.type="text/javascript",o.async=!0,o.src=i+"?sdkid="+e+"&lib="+t;
                var a=document.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)};
                ttq.load('${TIKTOK_PIXEL_ID}');
                ttq.page();
              }(window, document, 'ttq');
            `,
          }}
        />
      )}

      {/* Google Analytics 4 ----------------------------------------- */}
      {GA_ID && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
            strategy="afterInteractive"
          />
          <Script
            id="ga4"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
              __html: `
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${GA_ID}');
              `,
            }}
          />
        </>
      )}
    </>
  );
}

/**
 * Déclenche un événement de conversion sur les 3 réseaux (safe si pixel non configuré).
 *
 * @param event Nom de l'événement (Meta standard : PageView / Lead / CompleteRegistration / Contact)
 * @param params Paramètres additionnels (value, currency, etc.)
 */
export function firePixel(event: string, params: Record<string, any> = {}) {
  try {
    if (typeof window === 'undefined') return;
    // Meta
    if (window.fbq) {
      window.fbq('track', event, params);
    }
    // TikTok
    if (window.ttq) {
      window.ttq.track(event, params);
    }
    // GA4
    if (window.gtag) {
      window.gtag('event', event.toLowerCase(), params);
    }
  } catch (e) {
    // Silently fail — un blocker (uBlock/Brave) ne doit pas casser la page
  }
}
