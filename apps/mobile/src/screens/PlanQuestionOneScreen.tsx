import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useEffect, useState } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  type ImageSourcePropType,
  View,
} from 'react-native';
import {
  clampHouseholdCount,
  getContinueDisabled,
  PLAN_QUESTION_ONE_DEFAULTS,
  PLAN_QUESTION_ONE_MEAL_OPTIONS,
  PLAN_QUESTION_ONE_STEP_COUNT,
  type PlanQuestionOneMealId,
} from './planQuestionOneContent';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';

const ADULT_IMAGE = require('../../assets/plan-setup/icons/adult.png');
const CHILD_IMAGE = require('../../assets/plan-setup/icons/child.png');

const MEAL_ART: Record<PlanQuestionOneMealId, ImageSourcePropType> = {
  '3-5': require('../../assets/plan-setup/icons/meal-pot.png'),
  '6-9': require('../../assets/plan-setup/icons/meal-pan.png'),
  '10-14': require('../../assets/plan-setup/icons/meal-bowl.png'),
  other: require('../../assets/plan-setup/icons/meal-cutlery.png'),
};

const PLAN_QUESTION_ONE_COLORS = {
  background: priceCheckLocationTokens.colors.background,
  buttonTeal: '#087C7E',
  card: '#FFFEFC',
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  panel: '#F1FAF6',
  progressInactive: '#E9EDEC',
  selectedBorder: '#56C997',
  selectedCard: '#F0FFF4',
  control: '#F0F3F2',
  muted: priceCheckLocationTokens.colors.secondaryText,
  white: '#FFFFFF',
} as const;

const PLAN_QUESTION_ONE_FONT_ASSETS = priceCheckLocationFontAssets;
const PLAN_QUESTION_ONE_FONTS = priceCheckLocationFonts;

export interface PlanQuestionOneScreenProps {
  initialAdults?: number;
  initialChildren?: number;
  initialCustomMealCount?: number | null;
  initialSelectedMealId?: PlanQuestionOneMealId | null;
  isEditingSection?: boolean;
  stepCount?: number;
  onBack?: () => void;
  onContinue?: () => void;
  onStateChange?: (state: {
    adults: number;
    children: number;
    customMealCount: number | null;
    selectedMealId: PlanQuestionOneMealId | null;
  }) => void;
}

function QuestionnaireProgress({ stepCount }: { stepCount: number }) {
  return (
    <View
      accessibilityLabel={`Step 1 of ${stepCount}`}
      accessibilityRole="progressbar"
      accessibilityValue={{ max: stepCount, min: 0, now: 1 }}
      style={styles.progress}
    >
      {Array.from({ length: stepCount }, (_, index) => (
        <View
          key={`questionnaire-step-${index + 1}`}
          style={[styles.progressSegment, index === 0 && styles.progressSegmentActive]}
        />
      ))}
    </View>
  );
}

function HouseholdCounterRow({
  imageSource,
  label,
  onChange,
  value,
}: {
  imageSource: ImageSourcePropType;
  label: string;
  onChange: (delta: number) => void;
  value: number;
}) {
  return (
    <View style={styles.counterRow}>
      <View style={styles.avatarWrap}>
        <Image accessibilityElementsHidden source={imageSource} style={styles.avatar} />
      </View>
      <Text style={styles.counterLabel}>{label}</Text>
      <View style={styles.counterControls}>
        <Pressable
          accessibilityLabel={`Decrease ${label}`}
          accessibilityRole="button"
          onPress={() => onChange(-1)}
          style={({ pressed }) => [styles.counterButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={PLAN_QUESTION_ONE_COLORS.deepTeal} name="minus" size={23} />
        </Pressable>
        <Text accessibilityLabel={`${label}: ${value}`} style={styles.counterValue}>
          {value}
        </Text>
        <Pressable
          accessibilityLabel={`Increase ${label}`}
          accessibilityRole="button"
          onPress={() => onChange(1)}
          style={({ pressed }) => [styles.counterButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={PLAN_QUESTION_ONE_COLORS.deepTeal} name="plus" size={23} />
        </Pressable>
      </View>
    </View>
  );
}

function MealOptionCard({
  isSelected,
  onPress,
  option,
}: {
  isSelected: boolean;
  onPress: () => void;
  option: (typeof PLAN_QUESTION_ONE_MEAL_OPTIONS)[number];
}) {
  return (
    <Pressable
      accessibilityLabel={option.accessibilityLabel}
      accessibilityRole="button"
      accessibilityState={{ selected: isSelected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.mealCard,
        isSelected && styles.mealCardSelected,
        pressed && styles.mealCardPressed,
      ]}
    >
      <Image
        accessibilityElementsHidden
        resizeMode="contain"
        source={MEAL_ART[option.id]}
        style={styles.mealArt}
      />
      <Text style={styles.mealLabel}>
        {option.label}
      </Text>
      {option.supportingText ? <Text style={styles.mealSupporting}>{option.supportingText}</Text> : null}
      {isSelected ? (
        <View accessibilityElementsHidden style={styles.selectedCheck}>
          <MaterialCommunityIcons color={PLAN_QUESTION_ONE_COLORS.white} name="check" size={21} />
        </View>
      ) : null}
    </Pressable>
  );
}

export function PlanQuestionOneScreen({
  initialAdults = PLAN_QUESTION_ONE_DEFAULTS.adults,
  initialChildren = PLAN_QUESTION_ONE_DEFAULTS.children,
  initialCustomMealCount = null,
  initialSelectedMealId = PLAN_QUESTION_ONE_DEFAULTS.selectedMealId,
  isEditingSection = false,
  stepCount = PLAN_QUESTION_ONE_STEP_COUNT,
  onBack,
  onContinue,
  onStateChange,
}: PlanQuestionOneScreenProps) {
  const [fontsLoaded] = useFonts(PLAN_QUESTION_ONE_FONT_ASSETS);
  const [adults, setAdults] = useState<number>(initialAdults);
  const [children, setChildren] = useState<number>(initialChildren);
  const [selectedMealId, setSelectedMealId] = useState<PlanQuestionOneMealId | null>(initialSelectedMealId);
  const [customMealCount, setCustomMealCount] = useState<number | null>(
    initialSelectedMealId === 'other'
      ? Math.max(11, initialCustomMealCount ?? 11)
      : initialCustomMealCount,
  );

  useEffect(() => {
    onStateChange?.({ adults, children, customMealCount, selectedMealId });
  }, [adults, children, customMealCount, onStateChange, selectedMealId]);

  const selectMeal = (mealId: PlanQuestionOneMealId) => {
    setSelectedMealId(mealId);
    if (mealId === 'other') {
      setCustomMealCount((value) => Math.max(11, value ?? 11));
    } else {
      setCustomMealCount(null);
    }
  };

  const continueDisabled = getContinueDisabled(
    selectedMealId,
    customMealCount,
    adults,
    children,
  );

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Go back"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={PLAN_QUESTION_ONE_COLORS.deepTeal} name="arrow-left" size={28} />
          </Pressable>
          <View style={styles.headerCenter}>
            <Text style={styles.stepText}>Step 1 of {stepCount}</Text>
            <QuestionnaireProgress stepCount={stepCount} />
          </View>
        </View>

        <View style={styles.pageCopy}>
          <Text accessibilityRole="header" style={styles.pageTitle}>Your week</Text>
          <Text style={styles.pageSubtitle}>
            Tell us who you&apos;re planning for and how many meals we should cover.
          </Text>
        </View>

        <View style={styles.panel}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>Who are we planning for?</Text>
          <View style={styles.counterRows}>
            <HouseholdCounterRow
              imageSource={ADULT_IMAGE}
              label="Adults"
              onChange={(delta) => setAdults((value) => clampHouseholdCount(value, delta))}
              value={adults}
            />
            <HouseholdCounterRow
              imageSource={CHILD_IMAGE}
              label="Children"
              onChange={(delta) => setChildren((value) => clampHouseholdCount(value, delta))}
              value={children}
            />
          </View>
        </View>

        <View style={styles.panel}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            How many meals do you usually cook at home each week?
          </Text>
          <Text style={styles.mealDescription}>
            Count each time you prepare a main meal for your household.
          </Text>
          <View style={styles.mealGrid}>
            <View style={styles.mealGridRow}>
              {PLAN_QUESTION_ONE_MEAL_OPTIONS.slice(0, 2).map((option) => (
                <MealOptionCard
                  isSelected={selectedMealId === option.id}
                  key={option.id}
                  onPress={() => selectMeal(option.id)}
                  option={option}
                />
              ))}
            </View>
            <View style={styles.mealGridRow}>
              {PLAN_QUESTION_ONE_MEAL_OPTIONS.slice(2).map((option) => (
                <MealOptionCard
                  isSelected={selectedMealId === option.id}
                  key={option.id}
                  onPress={() => selectMeal(option.id)}
                  option={option}
                />
              ))}
            </View>
          </View>
        </View>

        <Pressable
          accessibilityLabel={isEditingSection ? 'Save changes' : 'Continue to Question 2'}
          accessibilityRole="button"
          accessibilityState={{ disabled: continueDisabled }}
          disabled={continueDisabled}
          onPress={onContinue}
          style={({ pressed }) => [
            styles.continueButton,
            continueDisabled && styles.continueButtonDisabled,
            pressed && styles.continueButtonPressed,
          ]}
        >
          <Text style={styles.continueText}>{isEditingSection ? 'Save changes' : 'Continue'}</Text>
          <MaterialCommunityIcons color={PLAN_QUESTION_ONE_COLORS.white} name="arrow-right" size={28} />
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: {
    height: 66,
    resizeMode: 'contain',
    width: 72,
  },
  avatarWrap: {
    alignItems: 'center',
    height: 66,
    justifyContent: 'center',
    width: 72,
  },
  content: {
    paddingBottom: 16,
    paddingHorizontal: 12,
    paddingTop: 2,
  },
  continueButton: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_ONE_COLORS.buttonTeal,
    borderRadius: 34,
    flexDirection: 'row',
    gap: 8,
    height: 58,
    justifyContent: 'center',
    marginTop: 14,
    width: '100%',
  },
  continueButtonDisabled: {
    backgroundColor: '#D8DFDD',
  },
  continueButtonPressed: {
    opacity: 0.86,
  },
  continueText: {
    color: PLAN_QUESTION_ONE_COLORS.white,
    fontFamily: PLAN_QUESTION_ONE_FONTS.bodySemibold,
    fontSize: 18,
    lineHeight: 22,
  },
  counterButton: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_ONE_COLORS.control,
    borderRadius: 24,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  counterControls: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    marginLeft: 'auto',
  },
  counterLabel: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_ONE_FONTS.body,
    fontSize: 18,
    lineHeight: 22,
    marginLeft: 8,
  },
  counterRow: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_ONE_COLORS.card,
    borderRadius: 18,
    flexDirection: 'row',
    minHeight: 76,
    paddingHorizontal: 8,
  },
  counterRows: {
    gap: 7,
    marginTop: 10,
  },
  counterValue: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.heading,
    fontSize: 24,
    lineHeight: 29,
    textAlign: 'center',
    width: 24,
  },
  customMealButton: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_ONE_COLORS.control,
    borderRadius: 24,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  customMealControls: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  customMealInput: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between',
    marginTop: 10,
  },
  customMealInputField: {
    backgroundColor: PLAN_QUESTION_ONE_COLORS.card,
    borderRadius: 24,
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.heading,
    fontSize: 20,
    height: 48,
    paddingHorizontal: 4,
    width: 56,
  },
  customMealLabel: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_ONE_FONTS.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  fontLoading: {
    backgroundColor: PLAN_QUESTION_ONE_COLORS.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    height: 68,
    justifyContent: 'center',
    position: 'relative',
  },
  headerButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    left: 0,
    position: 'absolute',
    top: 5,
    width: 48,
  },
  headerCenter: {
    alignItems: 'center',
    gap: 6,
  },
  mealArt: {
    height: 52,
    marginBottom: 2,
    resizeMode: 'contain',
    width: 70,
  },
  mealCard: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_ONE_COLORS.card,
    borderColor: 'transparent',
    borderRadius: 18,
    borderWidth: 2,
    flex: 1,
    height: 104,
    justifyContent: 'center',
    minWidth: 0,
    position: 'relative',
  },
  mealCardPressed: {
    opacity: 0.86,
  },
  mealCardSelected: {
    backgroundColor: PLAN_QUESTION_ONE_COLORS.selectedCard,
    borderColor: PLAN_QUESTION_ONE_COLORS.selectedBorder,
  },
  mealDescription: {
    color: PLAN_QUESTION_ONE_COLORS.muted,
    fontFamily: PLAN_QUESTION_ONE_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 5,
  },
  mealGrid: {
    gap: 8,
    marginTop: 10,
  },
  mealGridRow: {
    flexDirection: 'row',
    gap: 8,
  },
  mealLabel: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.heading,
    fontSize: 20,
    lineHeight: 24,
  },
  mealSupporting: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.body,
    fontSize: 15,
    lineHeight: 18,
  },
  pageCopy: {
    marginHorizontal: 8,
    marginTop: 2,
  },
  pageSubtitle: {
    color: PLAN_QUESTION_ONE_COLORS.muted,
    fontFamily: PLAN_QUESTION_ONE_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 5,
  },
  pageTitle: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.heading,
    fontSize: 28,
    lineHeight: 34,
  },
  panel: {
    backgroundColor: PLAN_QUESTION_ONE_COLORS.panel,
    borderRadius: 22,
    marginTop: 14,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  pressed: {
    opacity: 0.72,
  },
  progress: {
    flexDirection: 'row',
    gap: 6,
    height: 8,
    width: 174,
  },
  progressSegment: {
    backgroundColor: PLAN_QUESTION_ONE_COLORS.progressInactive,
    borderRadius: 5,
    flex: 1,
  },
  progressSegmentActive: {
    backgroundColor: priceCheckLocationTokens.colors.green,
  },
  sectionTitle: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.heading,
    fontSize: 20,
    lineHeight: 25,
  },
  selectedCheck: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 16,
    height: 28,
    justifyContent: 'center',
    position: 'absolute',
    right: 6,
    top: 6,
    width: 28,
  },
  screen: {
    backgroundColor: PLAN_QUESTION_ONE_COLORS.background,
    flex: 1,
  },
  skipButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    position: 'absolute',
    right: 0,
    top: 5,
    width: 58,
  },
  skipText: {
    color: PLAN_QUESTION_ONE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_ONE_FONTS.bodySemibold,
    fontSize: 18,
    lineHeight: 24,
  },
  stepText: {
    color: PLAN_QUESTION_ONE_COLORS.muted,
    fontFamily: PLAN_QUESTION_ONE_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
  },
});
