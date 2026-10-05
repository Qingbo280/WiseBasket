import { MaterialCommunityIcons } from '@expo/vector-icons';
import {
  Image,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { priceCheckLocationTokens } from '../components/price-check/priceCheckLocationTokens';
import { getMealsAtHomeLabel, type PlanDraft } from './planFlowContent';

const ADULT_SUMMARY_ART = require('../../assets/images/plan-questionnaire/adult.png');
const CHILD_SUMMARY_ART = require('../../assets/images/plan-questionnaire/child.png');
const MEAL_SUMMARY_ART = require('../../assets/images/plan-questionnaire/meals-6-9.png');

const COLORS = {
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  muted: priceCheckLocationTokens.colors.secondaryText,
  softGreen: '#F1FAF6',
} as const;

export function PlanSummary({
  planDraft,
  variant = 'default',
}: {
  planDraft: PlanDraft;
  variant?: 'default' | 'checkPrices';
}) {
  const householdParts = [
    planDraft.adults > 0
      ? `${planDraft.adults} ${planDraft.adults === 1 ? 'adult' : 'adults'}`
      : null,
    planDraft.children > 0
      ? `${planDraft.children} ${planDraft.children === 1 ? 'child' : 'children'}`
      : null,
  ].filter((part): part is string => part !== null);
  const household = householdParts.join(' · ') || '—';
  const budget = planDraft.weeklyBudget === null ? '—' : `RM ${planDraft.weeklyBudget}`;

  return (
    <View accessibilityLabel="Plan summary" style={[styles.profileSummary, variant === 'checkPrices' && styles.profileSummaryCheckPrices]}>
      <View style={[styles.profileCell, variant === 'checkPrices' && styles.profileCellCheckPrices]}>
        <MaterialCommunityIcons color={priceCheckLocationTokens.colors.green} name="wallet" size={26} />
        <View>
          <Text style={[styles.profileValue, variant === 'checkPrices' && styles.profileValueCheckPrices]}>{budget}</Text>
          <Text style={styles.profileLabel}>Budget</Text>
        </View>
      </View>
      <View style={[styles.profileDivider, variant === 'checkPrices' && styles.profileDividerCheckPrices]} />
      <View style={[styles.profileCell, variant === 'checkPrices' && styles.profileCellCheckPrices]}>
        <Image accessibilityElementsHidden source={MEAL_SUMMARY_ART} style={styles.profileMealArt} />
        <View>
          <Text style={[styles.profileValue, variant === 'checkPrices' && styles.profileValueCheckPrices]}>{getMealsAtHomeLabel(planDraft)}</Text>
          <Text style={styles.profileLabel}>Meals at home</Text>
        </View>
      </View>
      <View style={[styles.profileDivider, variant === 'checkPrices' && styles.profileDividerCheckPrices]} />
      <View style={[styles.profileCell, variant === 'checkPrices' && styles.profileCellCheckPrices]}>
        <View accessibilityElementsHidden style={styles.householdArt}>
          <Image source={ADULT_SUMMARY_ART} style={styles.householdArtImage} />
          <Image source={CHILD_SUMMARY_ART} style={[styles.householdArtImage, styles.householdArtChild]} />
        </View>
        <View>
          <Text style={[styles.profileValueSmall, variant === 'checkPrices' && styles.profileValueSmallCheckPrices]}>{household}</Text>
          <Text style={styles.profileLabel}>Household</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  householdArt: {
    alignItems: 'flex-end',
    flexDirection: 'row',
    height: 29,
    justifyContent: 'center',
    width: 29,
  },
  householdArtChild: {
    marginLeft: -4,
  },
  householdArtImage: {
    height: 23,
    resizeMode: 'contain',
    width: 19,
  },
  profileCell: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: 6,
    minWidth: 0,
  },
  profileCellCheckPrices: {
    gap: 6,
  },
  profileDivider: {
    backgroundColor: '#E1EBE4',
    height: 40,
    marginHorizontal: 4,
    width: 1,
  },
  profileDividerCheckPrices: {
    backgroundColor: '#E0EBE3',
    height: 32,
    marginHorizontal: 3,
  },
  profileLabel: {
    color: '#73827B',
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 10,
    lineHeight: 14,
    marginTop: 1,
  },
  profileMealArt: {
    height: 27,
    resizeMode: 'contain',
    width: 27,
  },
  profileSummary: {
    alignItems: 'center',
    backgroundColor: COLORS.softGreen,
    borderRadius: 18,
    flexDirection: 'row',
    minHeight: 78,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  profileSummaryCheckPrices: {
    backgroundColor: '#ECF8F1',
    borderColor: '#E5F0E7',
    borderRadius: 23,
    borderWidth: StyleSheet.hairlineWidth,
    boxShadow: '0px 3px 11px rgba(34, 83, 58, 0.06)',
    minHeight: 74,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  profileValue: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 17,
    lineHeight: 21,
  },
  profileValueCheckPrices: {
    fontSize: 17,
    lineHeight: 21,
  },
  profileValueSmall: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
    lineHeight: 16,
  },
  profileValueSmallCheckPrices: {
    fontSize: 13,
    lineHeight: 17,
  },
});
