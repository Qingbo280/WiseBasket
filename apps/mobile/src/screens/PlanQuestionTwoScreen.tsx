import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useEffect, useState } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type ImageSourcePropType,
  View,
} from 'react-native';
import {
  getContinueDisabled,
  isCustomRestrictionSelected,
  isSupportedRestriction,
  PLAN_QUESTION_TWO_BUDGET_OPTIONS,
  PLAN_QUESTION_TWO_DEFAULTS,
  PLAN_QUESTION_TWO_RESTRICTION_OPTIONS,
  PLAN_QUESTION_TWO_STEP_COUNT,
  parsePositiveBudgetInput,
  toggleRestriction,
  type PlanQuestionTwoRestrictionId,
} from './planQuestionTwoContent';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';

const RESTRICTION_ART: Partial<Record<PlanQuestionTwoRestrictionId, ImageSourcePropType>> = {
  dairy: require('../../assets/plan-setup/icons/restriction-dairy.png'),
  eggs: require('../../assets/plan-setup/icons/restriction-eggs.png'),
  gluten: require('../../assets/plan-setup/icons/restriction-gluten.png'),
  none: require('../../assets/plan-setup/icons/restriction-none.png'),
  other: require('../../assets/plan-setup/icons/other.png'),
  peanuts: require('../../assets/plan-setup/icons/restriction-peanuts.png'),
  pork: require('../../assets/plan-setup/icons/restriction-pork.png'),
};

const PLAN_QUESTION_TWO_COLORS = {
  background: priceCheckLocationTokens.colors.background,
  buttonTeal: '#087C7E',
  card: '#FFFEFC',
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  budgetPanel: '#F1FAF6',
  restrictionPanel: '#FFF8E9',
  progressInactive: '#E9EDEC',
  selectedBorder: '#56C997',
  selectedCard: '#F0FFF4',
  muted: priceCheckLocationTokens.colors.secondaryText,
  control: '#F0F3F2',
  white: '#FFFFFF',
} as const;

const PLAN_QUESTION_TWO_FONT_ASSETS = priceCheckLocationFontAssets;
const PLAN_QUESTION_TWO_FONTS = priceCheckLocationFonts;

export interface PlanQuestionTwoScreenProps {
  initialCustomRestriction?: string;
  initialSelectedRestrictions?: readonly PlanQuestionTwoRestrictionId[];
  initialWeeklyBudget?: number | null;
  isEditingSection?: boolean;
  stepCount?: number;
  onBack?: () => void;
  onContinue?: () => void;
  onStateChange?: (state: {
    customRestriction: string;
    selectedRestrictions: PlanQuestionTwoRestrictionId[];
    weeklyBudget: number | null;
  }) => void;
}

function QuestionnaireProgress({ stepCount }: { stepCount: number }) {
  return (
    <View
      accessibilityLabel={`Step 2 of ${stepCount}`}
      accessibilityRole="progressbar"
      accessibilityValue={{ max: stepCount, min: 0, now: 2 }}
      style={styles.progress}
    >
      {Array.from({ length: stepCount }, (_, index) => (
        <View
          key={`questionnaire-step-${index + 1}`}
          style={[styles.progressSegment, index < 2 && styles.progressSegmentActive]}
        />
      ))}
    </View>
  );
}

function BudgetOption({
  isSelected,
  onPress,
  value,
}: {
  isSelected: boolean;
  onPress: () => void;
  value: number;
}) {
  return (
    <Pressable
      accessibilityLabel={`RM ${value}`}
      accessibilityRole="button"
      accessibilityState={{ selected: isSelected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.budgetOption,
        isSelected && styles.budgetOptionSelected,
        pressed && styles.pressed,
      ]}
    >
      <Text style={styles.budgetOptionText}>RM {value}</Text>
    </Pressable>
  );
}

function RestrictionOption({
  isSelected,
  onPress,
  option,
}: {
  isSelected: boolean;
  onPress: () => void;
  option: (typeof PLAN_QUESTION_TWO_RESTRICTION_OPTIONS)[number];
}) {
  const imageSource = RESTRICTION_ART[option.id];
  const isSupported = isSupportedRestriction(option.id);

  return (
    <Pressable
      accessibilityLabel={option.label}
      accessibilityRole="button"
      accessibilityState={{ disabled: !isSupported, selected: isSelected }}
      disabled={!isSupported}
      onPress={onPress}
      style={({ pressed }) => [
        styles.restrictionOption,
        isSelected && styles.restrictionOptionSelected,
        !isSupported && styles.restrictionOptionDisabled,
        pressed && styles.pressed,
      ]}
    >
      {imageSource ? (
        <Image accessibilityElementsHidden source={imageSource} style={styles.restrictionArt} />
      ) : (
        <View style={styles.otherIcon}>
          <MaterialCommunityIcons color={PLAN_QUESTION_TWO_COLORS.deepTeal} name="plus" size={30} />
        </View>
      )}
      <Text style={styles.restrictionLabel}>{option.label}</Text>
      {isSelected && option.id !== 'none' ? (
        <View accessibilityElementsHidden style={styles.selectedCheck}>
          <MaterialCommunityIcons color={PLAN_QUESTION_TWO_COLORS.white} name="check" size={18} />
        </View>
      ) : null}
    </Pressable>
  );
}

export function PlanQuestionTwoScreen({
  initialCustomRestriction = PLAN_QUESTION_TWO_DEFAULTS.customRestriction,
  initialSelectedRestrictions = PLAN_QUESTION_TWO_DEFAULTS.selectedRestrictions,
  initialWeeklyBudget = PLAN_QUESTION_TWO_DEFAULTS.weeklyBudget,
  isEditingSection = false,
  stepCount = PLAN_QUESTION_TWO_STEP_COUNT,
  onBack,
  onContinue,
  onStateChange,
}: PlanQuestionTwoScreenProps) {
  const [fontsLoaded] = useFonts(PLAN_QUESTION_TWO_FONT_ASSETS);
  const [weeklyBudget, setWeeklyBudget] = useState<number | null>(initialWeeklyBudget);
  const [selectedBudget, setSelectedBudget] = useState<number | null>(
    PLAN_QUESTION_TWO_BUDGET_OPTIONS.includes(initialWeeklyBudget as (typeof PLAN_QUESTION_TWO_BUDGET_OPTIONS)[number])
      ? initialWeeklyBudget
      : null,
  );
  const [isBudgetEditing, setIsBudgetEditing] = useState(false);
  const [budgetInput, setBudgetInput] = useState(initialWeeklyBudget === null ? '' : String(initialWeeklyBudget));
  const [selectedRestrictions, setSelectedRestrictions] = useState<PlanQuestionTwoRestrictionId[]>(
    initialSelectedRestrictions.includes('none')
      ? ['none']
      : [...new Set(initialSelectedRestrictions)],
  );
  const [customRestriction, setCustomRestriction] = useState<string>(
    initialCustomRestriction,
  );

  useEffect(() => {
    onStateChange?.({ customRestriction, selectedRestrictions, weeklyBudget });
  }, [customRestriction, onStateChange, selectedRestrictions, weeklyBudget]);

  const selectQuickBudget = (value: number) => {
    setWeeklyBudget(value);
    setSelectedBudget(value);
    setBudgetInput(String(value));
    setIsBudgetEditing(false);
  };

  const beginBudgetEdit = () => {
    setBudgetInput(weeklyBudget === null ? '' : String(weeklyBudget));
    setSelectedBudget(null);
    setIsBudgetEditing(true);
  };

  const updateBudgetInput = (value: string) => {
    const digitsOnly = value.replace(/[^0-9]/g, '');
    const amount = parsePositiveBudgetInput(digitsOnly);
    setBudgetInput(digitsOnly);
    setWeeklyBudget(amount);
    setSelectedBudget(
      PLAN_QUESTION_TWO_BUDGET_OPTIONS.includes(amount as (typeof PLAN_QUESTION_TWO_BUDGET_OPTIONS)[number])
        ? amount
        : null,
    );
  };

  const selectRestriction = (restrictionId: PlanQuestionTwoRestrictionId) => {
    if (!isSupportedRestriction(restrictionId)) return;

    const isCurrentlySelected = selectedRestrictions.includes(restrictionId);

    setSelectedRestrictions(toggleRestriction(selectedRestrictions, restrictionId));

    if (restrictionId === 'none' || (restrictionId === 'other' && isCurrentlySelected)) {
      setCustomRestriction('');
    }
  };

  const customRestrictionSelected = isCustomRestrictionSelected(selectedRestrictions);
  const continueDisabled = getContinueDisabled(
    weeklyBudget,
    selectedRestrictions,
    customRestriction,
  );

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Go back"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={PLAN_QUESTION_TWO_COLORS.deepTeal} name="arrow-left" size={28} />
          </Pressable>
          <View style={styles.headerCenter}>
            <Text style={styles.stepText}>Step 2 of {stepCount}</Text>
            <QuestionnaireProgress stepCount={stepCount} />
          </View>
        </View>

        <View style={styles.pageCopy}>
          <Text accessibilityRole="header" style={styles.pageTitle}>Your budget &amp; needs</Text>
          <Text style={styles.pageSubtitle}>
            Set your weekly budget and anything we should avoid.
          </Text>
        </View>

        <View style={[styles.panel, styles.budgetPanel]}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>What&apos;s your weekly budget?</Text>
          <Text style={styles.budgetDescription}>
            How much can we spend on groceries for this plan?
          </Text>
          <View style={styles.budgetValueRow}>
            {isBudgetEditing ? (
              <View style={styles.budgetValueField}>
                <TextInput
                  accessibilityLabel="Weekly budget amount"
                  autoFocus
                  keyboardType="number-pad"
                  onChangeText={updateBudgetInput}
                  onSubmitEditing={() => setIsBudgetEditing(false)}
                  placeholder="RM —"
                  placeholderTextColor={PLAN_QUESTION_TWO_COLORS.muted}
                  returnKeyType="done"
                  style={styles.budgetValueInput}
                  value={budgetInput}
                />
                <MaterialCommunityIcons
                  color={PLAN_QUESTION_TWO_COLORS.deepTeal}
                  name="pencil-outline"
                  size={22}
                />
              </View>
            ) : (
              <Pressable
                accessibilityLabel="Edit weekly budget"
                accessibilityRole="button"
                onPress={beginBudgetEdit}
                style={({ pressed }) => [styles.budgetValueField, pressed && styles.pressed]}
              >
                <Text style={styles.budgetValueText}>RM {weeklyBudget ?? '—'}</Text>
                <MaterialCommunityIcons
                  color={PLAN_QUESTION_TWO_COLORS.deepTeal}
                  name="pencil-outline"
                  size={22}
                />
              </Pressable>
            )}
          </View>
          <Text style={styles.quickChoicesLabel}>Quick choices</Text>
          <View style={styles.budgetOptions}>
            {PLAN_QUESTION_TWO_BUDGET_OPTIONS.map((value) => (
              <BudgetOption
                isSelected={selectedBudget === value}
                key={value}
                onPress={() => selectQuickBudget(value)}
                value={value}
              />
            ))}
          </View>
        </View>

        <View style={[styles.panel, styles.restrictionPanel]}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>Anything we should avoid?</Text>
          <Text style={styles.restrictionDescription}>
            Select anything you don&apos;t want included in your plan.
          </Text>
          <View style={styles.restrictionGrid}>
            {PLAN_QUESTION_TWO_RESTRICTION_OPTIONS.map((option) => (
              <RestrictionOption
                isSelected={selectedRestrictions.includes(option.id)}
                key={option.id}
                onPress={() => selectRestriction(option.id)}
                option={option}
              />
            ))}
          </View>
          {customRestrictionSelected ? (
            <View style={styles.customRestrictionField}>
              <Text style={styles.customRestrictionLabel}>Other food or restriction</Text>
              <View style={styles.customRestrictionInputWrap}>
                <TextInput
                  accessibilityLabel="Other food or restriction"
                  onChangeText={setCustomRestriction}
                  placeholder="Type what we should avoid"
                  placeholderTextColor={PLAN_QUESTION_TWO_COLORS.muted}
                  style={styles.customRestrictionInput}
                  value={customRestriction}
                />
                {customRestriction.length > 0 ? (
                  <Pressable
                    accessibilityLabel="Clear other food or restriction"
                    accessibilityRole="button"
                    onPress={() => setCustomRestriction('')}
                    style={({ pressed }) => [styles.clearRestrictionButton, pressed && styles.pressed]}
                  >
                    <MaterialCommunityIcons color={PLAN_QUESTION_TWO_COLORS.muted} name="close" size={20} />
                  </Pressable>
                ) : null}
              </View>
            </View>
          ) : null}
        </View>

        <Pressable
          accessibilityLabel={isEditingSection ? 'Save changes' : 'Continue to Question 3'}
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
          <MaterialCommunityIcons color={PLAN_QUESTION_TWO_COLORS.white} name="arrow-right" size={28} />
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  budgetOption: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_TWO_COLORS.card,
    borderColor: 'transparent',
    borderRadius: 17,
    borderWidth: 2,
    flex: 1,
    height: 48,
    justifyContent: 'center',
    minWidth: 0,
  },
  budgetOptionSelected: {
    backgroundColor: PLAN_QUESTION_TWO_COLORS.selectedCard,
    borderColor: PLAN_QUESTION_TWO_COLORS.selectedBorder,
  },
  budgetDescription: {
    color: PLAN_QUESTION_TWO_COLORS.muted,
    fontFamily: PLAN_QUESTION_TWO_FONTS.body,
    fontSize: 14,
    lineHeight: 19,
    marginTop: 5,
  },
  budgetOptionText: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_TWO_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
  },
  budgetOptions: {
    flexDirection: 'row',
    gap: 7,
    marginTop: 7,
  },
  budgetPanel: {
    backgroundColor: PLAN_QUESTION_TWO_COLORS.budgetPanel,
  },
  budgetValueField: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_TWO_COLORS.card,
    borderColor: 'transparent',
    borderRadius: 17,
    borderWidth: 0,
    flexDirection: 'row',
    height: 66,
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    width: '100%',
  },
  budgetValueInput: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_TWO_FONTS.heading,
    fontSize: 32,
    height: 66,
    lineHeight: 38,
    paddingHorizontal: 0,
    paddingVertical: 0,
  },
  budgetValueRow: {
    marginTop: 10,
    width: '100%',
  },
  budgetValueText: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_TWO_FONTS.heading,
    fontSize: 32,
    lineHeight: 38,
  },
  continueButton: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_TWO_COLORS.buttonTeal,
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
    color: PLAN_QUESTION_TWO_COLORS.white,
    fontFamily: PLAN_QUESTION_TWO_FONTS.bodySemibold,
    fontSize: 18,
    lineHeight: 22,
  },
  clearRestrictionButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  content: {
    paddingBottom: 12,
    paddingHorizontal: 12,
    paddingTop: 2,
  },
  customRestrictionField: {
    marginTop: 10,
  },
  customRestrictionInput: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_TWO_FONTS.body,
    fontSize: 16,
    height: 48,
    lineHeight: 20,
    paddingHorizontal: 12,
    paddingVertical: 0,
  },
  customRestrictionInputWrap: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_TWO_COLORS.card,
    borderColor: '#DCE8E1',
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    height: 50,
    marginTop: 5,
  },
  customRestrictionLabel: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_TWO_FONTS.bodySemibold,
    fontSize: 15,
    lineHeight: 19,
  },
  fontLoading: {
    backgroundColor: PLAN_QUESTION_TWO_COLORS.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    height: 56,
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
  pageCopy: {
    marginHorizontal: 8,
    marginTop: 5,
  },
  pageSubtitle: {
    color: PLAN_QUESTION_TWO_COLORS.muted,
    fontFamily: PLAN_QUESTION_TWO_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 5,
  },
  pageTitle: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_TWO_FONTS.heading,
    fontSize: 28,
    lineHeight: 34,
  },
  panel: {
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
    backgroundColor: PLAN_QUESTION_TWO_COLORS.progressInactive,
    borderRadius: 5,
    flex: 1,
  },
  progressSegmentActive: {
    backgroundColor: priceCheckLocationTokens.colors.green,
  },
  quickChoicesLabel: {
    color: PLAN_QUESTION_TWO_COLORS.muted,
    fontFamily: PLAN_QUESTION_TWO_FONTS.bodySemibold,
    fontSize: 13,
    lineHeight: 17,
    marginTop: 9,
  },
  restrictionArt: {
    height: 40,
    marginRight: 8,
    resizeMode: 'contain',
    width: 40,
  },
  restrictionDescription: {
    color: PLAN_QUESTION_TWO_COLORS.muted,
    fontFamily: PLAN_QUESTION_TWO_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 5,
  },
  restrictionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 10,
  },
  restrictionLabel: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_TWO_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
  },
  restrictionOption: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_TWO_COLORS.card,
    borderColor: 'transparent',
    borderRadius: 17,
    borderWidth: 2,
    flexBasis: '48%',
    flexDirection: 'row',
    height: 56,
    minWidth: 0,
    paddingHorizontal: 8,
    position: 'relative',
  },
  restrictionOptionSelected: {
    backgroundColor: PLAN_QUESTION_TWO_COLORS.selectedCard,
    borderColor: PLAN_QUESTION_TWO_COLORS.selectedBorder,
  },
  restrictionOptionDisabled: {
    opacity: 0.48,
  },
  restrictionPanel: {
    backgroundColor: PLAN_QUESTION_TWO_COLORS.restrictionPanel,
  },
  screen: {
    backgroundColor: PLAN_QUESTION_TWO_COLORS.background,
    flex: 1,
  },
  sectionTitle: {
    color: PLAN_QUESTION_TWO_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_TWO_FONTS.heading,
    fontSize: 20,
    lineHeight: 25,
  },
  selectedCheck: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 14,
    height: 26,
    justifyContent: 'center',
    position: 'absolute',
    right: 6,
    top: 6,
    width: 26,
  },
  stepText: {
    color: PLAN_QUESTION_TWO_COLORS.muted,
    fontFamily: PLAN_QUESTION_TWO_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
  },
  otherIcon: {
    alignItems: 'center',
    height: 32,
    justifyContent: 'center',
    marginRight: 8,
    width: 32,
  },
});
