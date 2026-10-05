import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import type { ComponentProps } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { priceCheckLocationFontAssets, priceCheckLocationTokens } from '../components/price-check/priceCheckLocationTokens';
import type { PlanDraft } from './planFlowContent';
import { getMealsAtHomeLabel } from './planFlowContent';
import { PLAN_QUESTION_TWO_RESTRICTION_OPTIONS } from './planQuestionTwoContent';

const CONFIRMATION_ART = require('../../assets/images/price-check/brand-basket.png');

export type PlanSection = 'household' | 'budget' | 'foods';

export interface PlanConfirmationScreenProps {
  planDraft: PlanDraft;
  usualFoodNames: readonly string[];
  onEditSection: (section: PlanSection) => void;
  onBack: () => void;
  onConfirm: () => void;
}

function getHouseholdSummary(planDraft: PlanDraft): string {
  const adultLabel = `${planDraft.adults} ${planDraft.adults === 1 ? 'adult' : 'adults'}`;
  const childLabel = `${planDraft.children} ${planDraft.children === 1 ? 'child' : 'children'}`;
  return `${adultLabel} · ${childLabel}`;
}

function getRestrictionSummary(planDraft: PlanDraft): string {
  const restrictions = planDraft.selectedRestrictions
    .filter((id) => id !== 'none')
    .map((id) => {
      if (id === 'other' && planDraft.customRestriction.trim()) return planDraft.customRestriction.trim();
      return PLAN_QUESTION_TWO_RESTRICTION_OPTIONS.find((option) => option.id === id)?.label ?? id;
    });
  if (restrictions.length === 0) return 'No restrictions';
  const visible = restrictions.slice(0, 2);
  const remainder = restrictions.length - visible.length;
  return remainder > 0 ? `${visible.join(' · ')} · +${remainder}` : visible.join(' · ');
}

function SettingCard({
  detail,
  icon,
  onEdit,
  title,
  value,
}: {
  detail: string;
  icon: ComponentProps<typeof MaterialCommunityIcons>['name'];
  onEdit: () => void;
  title: string;
  value: string;
}) {
  return (
    <View style={styles.settingCard}>
      <View style={styles.settingHeader}>
        <View style={styles.settingTitleGroup}>
          <View style={styles.settingIconSurface}>
            <MaterialCommunityIcons color={COLORS.green} name={icon} size={18} />
          </View>
          <Text style={styles.settingTitle}>{title}</Text>
        </View>
        <Pressable
          accessibilityHint={`Opens only the ${title} settings.`}
          accessibilityLabel={`Edit ${title} settings`}
          accessibilityRole="button"
          onPress={onEdit}
          style={({ pressed }) => [styles.editButton, pressed && styles.pressed]}
        >
          <Text style={styles.editLabel}>Edit</Text>
          <MaterialCommunityIcons color={COLORS.green} name="chevron-right" size={19} />
        </Pressable>
      </View>
      <Text style={styles.settingValue}>{value}</Text>
      <Text style={styles.settingDetail}>{detail}</Text>
    </View>
  );
}

export function PlanConfirmationScreen({
  onBack,
  onConfirm,
  onEditSection,
  planDraft,
  usualFoodNames,
}: PlanConfirmationScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const canConfirm = planDraft.weeklyBudget !== null;
  const selectedFoodCount = planDraft.usualProductIds.length;
  const visibleFoodNames = usualFoodNames.slice(0, 4);
  const hiddenFoodCount = Math.max(0, selectedFoodCount - visibleFoodNames.length);
  const foodPreview = visibleFoodNames.length > 0
    ? `${visibleFoodNames.join(' · ')}${hiddenFoodCount > 0 ? ` · +${hiddenFoodCount}` : ''}`
    : selectedFoodCount > 0 ? 'Selected foods' : 'No usual foods selected';
  const foodCountLabel = `${selectedFoodCount} ${selectedFoodCount === 1 ? 'food' : 'foods'} selected`;
  const mealLabel = getMealsAtHomeLabel(planDraft);
  const budgetLabel = planDraft.weeklyBudget === null ? 'No budget set' : `RM ${planDraft.weeklyBudget} / week`;

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Back to previous page"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={29} />
          </Pressable>
          <Text accessibilityRole="header" style={styles.headerTitle}>Review your plan</Text>
          <View style={styles.headerSpacer} />
        </View>

        <View style={styles.heroRow}>
          <View style={styles.heroCopy}>
            <Text accessibilityRole="header" style={styles.title}>Check your details</Text>
            <Text style={styles.subtitle}>Make sure these look right before we build your next grocery plan.</Text>
          </View>
          <Image accessibilityLabel="WiseBasket basket illustration" resizeMode="contain" source={CONFIRMATION_ART} style={styles.hero} />
        </View>

        <View style={styles.settingsSection}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>Your current settings</Text>
          <View style={styles.settingsList}>
            <SettingCard
              detail={`${mealLabel} meals / week`}
              icon="account-group-outline"
              onEdit={() => onEditSection('household')}
              title="Household & meals"
              value={getHouseholdSummary(planDraft)}
            />
            <SettingCard
              detail={getRestrictionSummary(planDraft)}
              icon="wallet-outline"
              onEdit={() => onEditSection('budget')}
              title="Budget & needs"
              value={budgetLabel}
            />
            <SettingCard
              detail={foodPreview}
              icon="basket-outline"
              onEdit={() => onEditSection('foods')}
              title="Usual foods"
              value={foodCountLabel}
            />
          </View>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          accessibilityLabel={canConfirm ? 'Confirm and build plan' : 'Set a budget first'}
          accessibilityRole="button"
          accessibilityState={{ disabled: !canConfirm }}
          disabled={!canConfirm}
          onPress={onConfirm}
          style={({ pressed }) => [
            styles.confirmButton,
            !canConfirm && styles.confirmButtonDisabled,
            pressed && canConfirm && styles.pressed,
          ]}
        >
          <View style={styles.confirmButtonContent}>
            <Text style={styles.confirmButtonText}>{canConfirm ? 'Confirm & build plan' : 'Set a budget first'}</Text>
            <MaterialCommunityIcons color={COLORS.white} name="arrow-right" size={23} />
          </View>
        </Pressable>
      </View>
    </View>
  );
}

const COLORS = {
  background: '#FBFBF6',
  card: '#FFFFFF',
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  green: '#0F8A83',
  muted: priceCheckLocationTokens.colors.secondaryText,
  primary: '#0F8A83',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  confirmButton: {
    alignItems: 'center',
    backgroundColor: COLORS.primary,
    borderRadius: 25,
    justifyContent: 'center',
    minHeight: 54,
    paddingHorizontal: 16,
  },
  confirmButtonDisabled: {
    backgroundColor: '#9BAAA5',
  },
  confirmButtonText: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 16,
    includeFontPadding: false,
    lineHeight: 22,
    flexShrink: 1,
    textAlign: 'center',
  },
  confirmButtonContent: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    maxWidth: '100%',
  },
  content: {
    gap: 9,
    paddingBottom: 22,
    paddingHorizontal: 20,
    paddingTop: 2,
  },
  scrollView: {
    flex: 1,
  },
  editButton: {
    alignItems: 'center',
    backgroundColor: 'transparent',
    borderRadius: 16,
    flexDirection: 'row',
    gap: 1,
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 64,
    paddingHorizontal: 6,
  },
  editLabel: {
    color: COLORS.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
    lineHeight: 16,
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  footer: {
    backgroundColor: COLORS.background,
    borderTopColor: '#E7EEE9',
    borderTopWidth: 1,
    paddingBottom: 14,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 58,
  },
  headerButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  headerSpacer: {
    width: 48,
  },
  headerTitle: {
    color: COLORS.deepTeal,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 20,
    lineHeight: 27,
    textAlign: 'center',
  },
  hero: {
    height: 82,
    width: 104,
  },
  heroCopy: {
    flex: 1,
    gap: 3,
    minWidth: 0,
  },
  heroRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    minHeight: 96,
  },
  sectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 16,
    lineHeight: 22,
    marginTop: 2,
  },
  settingCard: {
    backgroundColor: COLORS.card,
    borderColor: '#EAF0E8',
    borderRadius: 22,
    borderWidth: 1,
    boxShadow: '0px 4px 12px rgba(37, 72, 51, 0.06)',
    paddingHorizontal: 13,
    paddingVertical: 10,
  },
  settingDetail: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 3,
  },
  settingHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
    minHeight: 44,
  },
  settingIconSurface: {
    alignItems: 'center',
    backgroundColor: '#F4FAF6',
    borderRadius: 12,
    height: 34,
    justifyContent: 'center',
    width: 34,
  },
  settingTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    flexShrink: 1,
    fontSize: 14,
    lineHeight: 19,
  },
  settingTitleGroup: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    minWidth: 0,
  },
  settingValue: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 0,
  },
  settingsList: {
    gap: 12,
  },
  settingsSection: {
    gap: 8,
  },
  pressed: {
    opacity: 0.78,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  subtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 19,
  },
  title: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 21,
    lineHeight: 27,
  },
});
