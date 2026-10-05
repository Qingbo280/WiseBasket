// Web testing / UAT rendering only. IntroScreen.tsx remains the native screen.
import { useEffect, useRef, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import type { IntroScreenProps } from './IntroScreen';
import { introPosterLayout } from './introPosterLayout';

const INTRO_PAGES = [
  { source: require('../../assets/images/intro/06_intro_01.png'), width: 863, height: 1822 },
  { source: require('../../assets/images/intro/06_intro_02.png'), width: 864, height: 1821 },
];
const LOGO_IMAGE = require('../../assets/images/brand/wisebasket-logo-horizontal.png');

// Fit the poster once, then anchor the logo and hit areas to its actual bounds.
export function IntroScreen({ initialPage = 0, onComplete }: IntroScreenProps) {
  const windowSize = useWindowDimensions();
  const [size, setSize] = useState({ width: windowSize.width, height: windowSize.height });
  const [page, setPage] = useState(Math.max(0, Math.min(initialPage, 1)));
  const pager = useRef<ScrollView>(null);
  const currentPage = useRef(page);

  useEffect(() => {
    // Run after the new page widths have been committed to the DOM.
    pager.current?.scrollTo({ x: size.width * currentPage.current, animated: false });
  }, [size.width, size.height]);

  const next = (index: number) => {
    if (index === INTRO_PAGES.length - 1) {
      onComplete(index);
    } else {
      currentPage.current = index + 1;
      setPage(index + 1);
      pager.current?.scrollTo({ x: size.width * (index + 1), animated: true });
    }
  };

  return (
    <View style={styles.screen}>
      <View style={styles.artwork} onLayout={({ nativeEvent }) => {
        const { width, height } = nativeEvent.layout;
        if (width > 0 && height > 0) {
          setSize((previous) => previous.width === width && previous.height === height
            ? previous : { width, height });
        }
      }}>
      <ScrollView
        ref={pager}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        style={StyleSheet.absoluteFill}
        contentContainerStyle={{ height: size.height }}
        onScroll={({ nativeEvent }) => {
          const index = Math.max(0, Math.min(Math.round(nativeEvent.contentOffset.x / size.width), 1));
          currentPage.current = index;
          setPage(index);
        }}
        scrollEventThrottle={16}
      >
        {INTRO_PAGES.map((poster, index) => {
          const layout = introPosterLayout(size, poster);
          const { width, height } = layout;
          return (
            <View key={index} style={[styles.page, { width: size.width, height: size.height }]}>
              <View style={{ width, height }}>
                <Image source={poster.source} resizeMode="contain" style={{ width, height }} />
                <Image source={LOGO_IMAGE} accessibilityLabel="WiseBasket" resizeMode="contain"
                  style={{ position: 'absolute', ...layout.logo }} />
                <Pressable accessibilityLabel="Skip introduction" accessibilityRole="button"
                  onPress={() => onComplete(index)}
                  style={{ position: 'absolute', ...layout.skip }} />
                <Pressable accessibilityLabel={index === 1 ? 'Start WiseBasket' : 'Next introduction page'}
                  accessibilityRole="button" onPress={() => next(index)}
                  style={{ position: 'absolute', ...layout.next }} />
              </View>
            </View>
          );
        })}
      </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FEFDFA' },
  artwork: { flex: 1, minHeight: 0 },
  page: { flexShrink: 0, alignItems: 'center', justifyContent: 'center' },
});
