import { useRef, useState } from 'react';
import {
  FlatList,
  Image,
  Pressable,
  StyleSheet,
  useWindowDimensions,
  View,
  type ImageSourcePropType,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';

const INTRO_PAGE_1 = require('../../assets/images/intro/06_intro_01.png');
const INTRO_PAGE_2 = require('../../assets/images/intro/06_intro_02.png');
const LOGO_IMAGE = require('../../assets/images/brand/wisebasket-logo-horizontal.png');

const INTRO_PAGES = [
  { image: INTRO_PAGE_1, key: 'intro-page-1' },
  { image: INTRO_PAGE_2, key: 'intro-page-2' },
] as const;

export interface IntroScreenProps {
  initialPage?: number;
  onComplete: (pageIndex: number) => void;
}

type IntroPage = (typeof INTRO_PAGES)[number];

export function IntroScreen({ initialPage = 0, onComplete }: IntroScreenProps) {
  const { width } = useWindowDimensions();
  const initialPageIndex = Math.max(0, Math.min(initialPage, INTRO_PAGES.length - 1));
  const [currentPage, setCurrentPage] = useState(initialPageIndex);
  const pagerRef = useRef<FlatList<IntroPage>>(null);
  const pageWidth = Math.max(width, 1);

  const handleScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const nextPage = Math.round(event.nativeEvent.contentOffset.x / pageWidth);
    setCurrentPage(Math.max(0, Math.min(nextPage, INTRO_PAGES.length - 1)));
  };

  const handleNextPress = () => {
    if (currentPage === INTRO_PAGES.length - 1) {
      onComplete(currentPage);
      return;
    }

    pagerRef.current?.scrollToIndex({ animated: true, index: currentPage + 1 });
  };

  return (
    <View style={styles.screen}>
      <FlatList
        ref={pagerRef}
        data={INTRO_PAGES}
        getItemLayout={(_, index) => ({ index, length: pageWidth, offset: pageWidth * index })}
        horizontal
        initialScrollIndex={initialPageIndex}
        initialNumToRender={INTRO_PAGES.length}
        keyExtractor={(item) => item.key}
        onMomentumScrollEnd={handleScrollEnd}
        pagingEnabled
        renderItem={({ item }) => <IntroPageImage item={item} pageWidth={pageWidth} />}
        showsHorizontalScrollIndicator={false}
        style={StyleSheet.absoluteFill}
      />

      <Pressable
        accessibilityLabel="Skip introduction"
        accessibilityRole="button"
        onPress={() => onComplete(currentPage)}
        style={styles.skipHitArea}
      />

      <Pressable
        accessibilityLabel={currentPage === INTRO_PAGES.length - 1 ? 'Start WiseBasket' : 'Next introduction page'}
        accessibilityRole="button"
        onPress={handleNextPress}
        style={styles.nextHitArea}
      />
    </View>
  );
}

function IntroPageImage({ item, pageWidth }: { item: IntroPage; pageWidth: number }) {
  return (
    <View style={[styles.page, { width: pageWidth }]}>
      <Image accessibilityElementsHidden resizeMode="cover" source={item.image} style={styles.pageImage} />
      <View pointerEvents="none" style={styles.pageLogoLayer}>
        <Image
          accessibilityLabel="WiseBasket"
          resizeMode="contain"
          source={LOGO_IMAGE}
          style={styles.pageLogo}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  pageLogoLayer: {
    left: 0,
    position: 'absolute',
    top: 0,
  },
  pageLogo: {
    height: 30,
    left: 14,
    position: 'absolute',
    top: 14,
    width: 116,
  },
  nextHitArea: {
    bottom: 10,
    height: 88,
    position: 'absolute',
    right: 12,
    width: 88,
  },
  page: {
    flex: 1,
  },
  pageImage: {
    height: '100%',
    width: '100%',
  },
  screen: {
    backgroundColor: '#FEFDFA',
    flex: 1,
  },
  skipHitArea: {
    height: 58,
    position: 'absolute',
    right: 12,
    top: 32,
    width: 84,
  },
});
