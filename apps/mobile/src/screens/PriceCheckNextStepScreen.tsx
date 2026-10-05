import { useFonts } from 'expo-font';
import { Image, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { NextStepOptionCard } from '../components/price-check/NextStepOptionCard';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import {
  PRICE_CHECK_NEXT_STEP_OPTIONS,
  getPriceCheckNextStepHeroHeight,
  type PriceCheckNextStepOptionId,
} from './priceCheckNextStepContent';

const HERO_IMAGE = require('../../assets/images/price-check-next-step/hero-next-step.png');

export interface PriceCheckNextStepScreenProps {
  onCheckAnotherItem: () => void;
  onFinishForNow: () => void;
  onPlanNextWeek: () => void;
}

export function PriceCheckNextStepScreen({
  onCheckAnotherItem,
  onFinishForNow,
  onPlanNextWeek,
}: PriceCheckNextStepScreenProps) {
  const { width } = useWindowDimensions();
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const horizontalPadding = width <= 360 ? 20 : width <= 384 ? 22 : 24;

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  const handleOptionPress = (optionId: PriceCheckNextStepOptionId) => {
    if (optionId === 'check-another-item') {
      onCheckAnotherItem();
      return;
    }

    if (optionId === 'plan-next-week') {
      onPlanNextWeek();
      return;
    }

    onFinishForNow();
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={[styles.content, { paddingHorizontal: horizontalPadding }]}
        showsVerticalScrollIndicator={false}
      >
        <Image
          accessibilityLabel="WiseBasket checked item illustration"
          resizeMode="contain"
          source={HERO_IMAGE}
          style={[
            styles.hero,
            {
              height: getPriceCheckNextStepHeroHeight(width),
              marginLeft: -horizontalPadding,
              width,
            },
          ]}
        />

        <Text accessibilityRole="header" style={styles.heading}>
          What would you like{`\n`}to do next?
        </Text>
        <Text style={styles.supportingCopy}>
          You can keep comparing prices, start planning next week’s groceries, or stop here for now.
        </Text>

        <View style={styles.options}>
          {PRICE_CHECK_NEXT_STEP_OPTIONS.map((option) => (
            <NextStepOptionCard
              icon={option.icon}
              key={option.id}
              onPress={() => handleOptionPress(option.id)}
              supportingText={option.supportingText}
              title={option.title}
              visualVariant={option.visualVariant}
            />
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingBottom: 28,
  },
  fontLoading: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  heading: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 35,
    lineHeight: 40,
    marginTop: 10,
  },
  hero: {
    alignSelf: 'center',
  },
  options: {
    gap: 12,
    marginTop: 18,
  },
  screen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  supportingCopy: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 16,
    lineHeight: 23,
    marginTop: 9,
  },
});
