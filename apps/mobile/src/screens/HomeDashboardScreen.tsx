import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { Image as CachedImage } from 'expo-image';
import type { ComponentProps } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  type StyleProp,
  Text,
  type TextStyle,
  useWindowDimensions,
  View,
} from 'react-native';

import {
  DASHBOARD_LAYOUT,
  DASHBOARD_TYPE_SCALE,
  getDashboardGreeting,
  getDashboardHorizontalPadding,
  getRecentCheckPreview,
  type DashboardRecentCheck,
} from './homeDashboardContent';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
} from '../components/price-check/priceCheckLocationTokens';
import {
  temporaryBoxStyle,
  temporaryIconSize,
  temporaryIconStyle,
  temporaryImageStyle,
  temporaryNumber,
  temporaryResizeMode,
  temporaryTextStyle,
  useTemporaryDevUIValues,
  type TemporaryDevUIValues,
} from '../devUITemporary';
import { PlanSummary } from './PlanSummary';
import type { PlanDraft } from './planFlowContent';
import {
  getLocationDisplayLabel,
  type ConfirmedLocation,
} from '../services/confirmedLocationContent';

const LOGO_IMAGE = require('../../assets/images/brand/wisebasket-logo-horizontal.png');
const HOME_MASCOT_IMAGE = require('../../assets/illustrations/home-mascot-search.png');
const COMPARE_PRICES_IMAGE = require('../../assets/illustrations/compare-prices-3d.png');
const PLAN_GROCERIES_IMAGE = require('../../assets/illustrations/plan-groceries-3d.png');
const SHOPPING_TIP_BANNER_IMAGE = require('../../assets/images/dashboard/03_tips.jpg');

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

export interface HomeDashboardScreenProps {
  confirmedLocation?: ConfirmedLocation | null;
  displayName?: string | null;
  onBasketPress?: () => void;
  onCreatePlanPress?: () => void;
  onLocationPress?: () => void;
  onPlanPress?: () => void;
  onPriceCheckPress: () => void;
  onProfilePress?: () => void;
  planDraft?: PlanDraft | null;
  recentChecks: readonly DashboardRecentCheck[];
}

function DashboardIcon({
  color,
  name,
  size = 24,
  style,
}: {
  color: string;
  name: IconName;
  size?: number;
  style?: StyleProp<TextStyle>;
}) {
  return <MaterialCommunityIcons accessibilityElementsHidden color={color} name={name} size={size} style={style} />;
}

function DashboardHeader({
  devUI,
  onProfilePress,
}: Pick<HomeDashboardScreenProps, 'onProfilePress'> & { devUI: TemporaryDevUIValues | null }) {
  return (
    <View style={[styles.header, temporaryBoxStyle(devUI, 'headerContainer', { heightMode: 'height' })]}>
      <Image
        accessibilityLabel="WiseBasket"
        resizeMode={temporaryResizeMode(devUI, 'logo', 'contain')}
        source={LOGO_IMAGE}
        style={[styles.logo, temporaryImageStyle(devUI, 'logo')]}
      />
      <Pressable
        accessibilityLabel="Profile"
        accessibilityRole="button"
        accessibilityState={{ disabled: !onProfilePress }}
        disabled={!onProfilePress}
        onPress={onProfilePress}
        style={({ pressed }) => [
          styles.profileButton,
          temporaryBoxStyle(devUI, 'profileButton'),
          pressed && styles.pressed,
        ]}
      >
        <DashboardIcon
          color={COLORS.deepTeal}
          name="account-circle-outline"
          size={temporaryIconSize(devUI, 'profileIcon', 34)}
          style={temporaryIconStyle(devUI, 'profileIcon')}
        />
      </Pressable>
    </View>
  );
}

function DashboardLocationCard({
  confirmedLocation,
  onLocationPress: onPress,
}: Pick<HomeDashboardScreenProps, 'confirmedLocation' | 'onLocationPress'>) {
  const hasConfirmedLocation = Boolean(confirmedLocation);
  const locationLabel = confirmedLocation
    ? getLocationDisplayLabel(confirmedLocation)
    : 'Set your shopping location';

  return (
    <Pressable
      accessibilityLabel={hasConfirmedLocation ? `Change shopping location, ${locationLabel}` : 'Set your shopping location'}
      accessibilityRole="button"
      accessibilityState={{ disabled: !onPress }}
      disabled={!onPress}
      onPress={onPress}
      style={({ pressed }) => [styles.locationCard, pressed && styles.pressed]}
    >
      <View style={styles.locationCardMain}>
        <View style={styles.locationIcon}>
          <DashboardIcon color={COLORS.white} name="map-marker" size={28} />
        </View>
        <View style={styles.locationCopy}>
          <Text style={styles.locationCaption}>{hasConfirmedLocation ? 'Shopping near' : 'Location'}</Text>
          <Text style={styles.locationValue}>{locationLabel}</Text>
        </View>
      </View>
      <View style={styles.locationChevron}>
        <DashboardIcon color={COLORS.deepTeal} name="chevron-right" size={30} />
      </View>
    </Pressable>
  );
}

function QuickActionCard({
  disabled,
  illustration,
  onPress,
  supportingText,
  title,
  tone,
  devUI,
}: {
  disabled?: boolean;
  illustration: number;
  onPress?: () => void;
  supportingText: string;
  title: string;
  tone: 'orange' | 'green';
  devUI: TemporaryDevUIValues | null;
}) {
  const target = tone === 'orange' ? 'priceAction' : 'planAction';

  return (
    <Pressable
      accessibilityLabel={title}
      accessibilityRole="button"
      accessibilityState={{ disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionCard,
        tone === 'orange' ? styles.actionCardOrange : styles.actionCardGreen,
        temporaryBoxStyle(devUI, `${target}Card`),
        pressed && styles.pressed,
      ]}
    >
      <View
        pointerEvents="none"
        style={[
          styles.actionIllustrationWrap,
          tone === 'orange'
            ? styles.actionIllustrationCompare
            : styles.actionIllustrationPlan,
        ]}
      >
        <Image
          accessible={false}
          resizeMode="contain"
          source={illustration}
          style={[
            styles.actionIllustration,
            tone === 'orange'
              ? styles.actionIllustrationCompareImage
              : styles.actionIllustrationPlanImage,
          ]}
        />
      </View>
      <View style={styles.actionCopy}>
        <Text
          numberOfLines={3}
          style={[styles.actionTitle, temporaryTextStyle(devUI, `${target}Title`)]}
        >
          {title}
        </Text>
        <Text
          style={[
            styles.actionSupporting,
            temporaryTextStyle(devUI, `${target}Body`),
          ]}
        >
          {supportingText}
        </Text>
      </View>
      <View style={styles.actionArrow}>
        <DashboardIcon color={COLORS.deepTeal} name="arrow-right" size={22} />
      </View>
    </Pressable>
  );
}

function SectionHeading({
  devUI,
  icon,
  title,
  tuningKey,
}: {
  devUI: TemporaryDevUIValues | null;
  icon: IconName;
  title: string;
  tuningKey: 'quickSectionHeading' | 'weeklySectionHeading' | 'recentSectionHeading';
}) {
  return (
    <View style={[
      styles.sectionHeading,
      tuningKey === 'weeklySectionHeading' && styles.weeklySectionHeading,
      temporaryBoxStyle(devUI, `${tuningKey}Container`, { heightMode: 'minHeight' }),
    ]}>
      <View style={[styles.sectionHeadingTitle, temporaryBoxStyle(devUI, `${tuningKey}Title`)]}>
        <DashboardIcon
          color={COLORS.deepTeal}
          name={icon}
          size={temporaryIconSize(devUI, `${tuningKey}Icon`, 25)}
          style={temporaryIconStyle(devUI, `${tuningKey}Icon`)}
        />
        <Text
          accessibilityRole="header"
          style={[
            styles.sectionTitle,
            temporaryTextStyle(devUI, `${tuningKey}Text`),
          ]}
        >
          {title}
        </Text>
      </View>
    </View>
  );
}

function EmptyPlanCard({
  onCreatePlanPress,
}: {
  onCreatePlanPress?: () => void;
}) {
  return (
    <Pressable
      accessibilityLabel="Create a plan"
      accessibilityRole="button"
      accessibilityState={{ disabled: !onCreatePlanPress }}
      disabled={!onCreatePlanPress}
      onPress={onCreatePlanPress}
      style={({ pressed }) => [styles.planStatusCard, pressed && styles.pressed]}
    >
      <Text style={styles.planStatusTitle}>No plan yet</Text>
      <Text style={styles.planStatusDescription}>
        Plan next week’s groceries based on your budget and household.
      </Text>
      <View style={styles.planStatusAction}>
        <Text style={styles.planStatusActionText}>Create a plan</Text>
        <DashboardIcon color={COLORS.deepTeal} name="arrow-right" size={21} />
      </View>
    </Pressable>
  );
}

function ActivePlanCard({ onPress, planDraft }: { onPress?: () => void; planDraft: PlanDraft }) {
  return (
    <Pressable
      accessibilityLabel="Weekly plan summary"
      accessibilityRole="button"
      accessibilityState={{ disabled: !onPress }}
      disabled={!onPress}
      onPress={onPress}
      style={({ pressed }) => [styles.activePlanPressable, pressed && styles.pressed]}
    >
      <PlanSummary planDraft={planDraft} />
    </Pressable>
  );
}

function WeeklyPlanSection({
  devUI,
  onBasketPress,
  onCreatePlanPress,
  planDraft,
}: Pick<HomeDashboardScreenProps, 'onBasketPress' | 'onCreatePlanPress' | 'planDraft'> & {
  devUI: TemporaryDevUIValues | null;
}) {
  return (
    <View style={[styles.section, { marginTop: temporaryNumber(devUI, 'weeklyPlanSectionMarginTop', 24) }]}>
      <SectionHeading devUI={devUI} icon="calendar-month-outline" title="This week's plan" tuningKey="weeklySectionHeading" />
      {planDraft ? (
        <ActivePlanCard onPress={onBasketPress} planDraft={planDraft} />
      ) : (
        <EmptyPlanCard onCreatePlanPress={onCreatePlanPress} />
      )}
    </View>
  );
}

function RecentCheckCard({ check, devUI, width }: { check: DashboardRecentCheck; devUI: TemporaryDevUIValues | null; width: number }) {
  const resizeMode = temporaryResizeMode(devUI, 'recentProductImage', 'contain');
  const contentFit = resizeMode === 'stretch'
    ? 'fill'
    : resizeMode === 'center'
      ? 'none'
      : resizeMode;

  return (
    <View
      accessibilityLabel={`${check.productName}${check.priceLabel ? `, ${check.priceLabel}` : ''}`}
      style={[styles.recentCard, { width }, temporaryBoxStyle(devUI, 'recentCard', { heightMode: 'minHeight' })]}
    >
      <View style={[styles.recentImageWrap, temporaryBoxStyle(devUI, 'recentProductImageWrap')]}>
        <CachedImage
          accessibilityLabel={`${check.productName} product image`}
          cachePolicy="memory-disk"
          contentFit={contentFit}
          source={check.imageSource}
          style={[styles.recentImage, temporaryImageStyle(devUI, 'recentProductImage')]}
        />
      </View>
      <Text numberOfLines={2} style={[styles.recentProductName, temporaryTextStyle(devUI, 'recentProductName')]}>{check.productName}</Text>
      {check.priceLabel ? <Text style={[styles.recentPrice, temporaryTextStyle(devUI, 'recentPrice')]}>{check.priceLabel}</Text> : null}
      {check.storeName ? <Text numberOfLines={1} style={[styles.recentStore, temporaryTextStyle(devUI, 'recentStore')]}>{check.storeName}</Text> : null}
      {check.distanceLabel ? (
        <View style={[styles.recentDistanceRow, temporaryBoxStyle(devUI, 'recentDistanceRow')]}>
          <DashboardIcon
            color={COLORS.orange}
            name="map-marker"
            size={temporaryIconSize(devUI, 'recentDistanceIcon', 15)}
            style={temporaryIconStyle(devUI, 'recentDistanceIcon')}
          />
          <Text numberOfLines={1} style={[styles.recentDistance, temporaryTextStyle(devUI, 'recentDistance')]}>{check.distanceLabel}</Text>
        </View>
      ) : null}
    </View>
  );
}

function RecentlyCheckedSection({
  devUI,
  horizontalPadding,
  recentChecks,
}: {
  devUI: TemporaryDevUIValues | null;
  horizontalPadding: number;
  recentChecks: HomeDashboardScreenProps['recentChecks'];
}) {
  const { width } = useWindowDimensions();
  const cardWidth = Math.max(98, Math.min(118, Math.round((width - horizontalPadding * 2 - 20) / 3)));
  const preview = getRecentCheckPreview(recentChecks);

  if (preview.length === 0) return null;

  return (
    <View style={[styles.section, { marginTop: temporaryNumber(devUI, 'recentSectionMarginTop', 24) }]}>
      <SectionHeading devUI={devUI} icon="clock-outline" title="Recently checked" tuningKey="recentSectionHeading" />
      <ScrollView
        contentContainerStyle={[styles.recentRow, temporaryBoxStyle(devUI, 'recentRow')]}
        horizontal
        showsHorizontalScrollIndicator={false}
      >
        {preview.map((check) => <RecentCheckCard check={check} devUI={devUI} key={check.id} width={temporaryNumber(devUI, 'recentCardWidth', 0) || cardWidth} />)}
      </ScrollView>
    </View>
  );
}

function ShoppingTipCard({
  devUI,
  horizontalPadding,
  viewportWidth,
}: {
  devUI: TemporaryDevUIValues | null;
  horizontalPadding: number;
  viewportWidth: number;
}) {
  const bannerWidth = Math.max(0, viewportWidth - horizontalPadding * 2);
  const bannerHeight = bannerWidth / (1370 / 346);

  return (
    <View style={[styles.section, { marginTop: temporaryNumber(devUI, 'tipSectionMarginTop', 16) }]}>
      <View style={[styles.tipHeading, temporaryBoxStyle(devUI, 'tipHeading', { heightMode: 'minHeight' })]}>
        <Text
          accessibilityRole="header"
          style={[
            styles.sectionTitle,
            temporaryTextStyle(devUI, 'tipHeadingText'),
          ]}
        >
          Tips for brighter shopping
        </Text>
      </View>
      <Image
        accessibilityLabel="Seasonal vegetables can help. In-season produce is often fresher and can be better value."
        resizeMode="cover"
        source={SHOPPING_TIP_BANNER_IMAGE}
        style={[styles.tipBanner, { height: bannerHeight }]}
      />
    </View>
  );
}

type DashboardTab = 'home' | 'basket';

export function DashboardBottomNavigation({
  activeTab = 'home',
  devUI,
  onBasketPress,
  onHomePress,
  onPriceCheckPress,
}: Pick<HomeDashboardScreenProps, 'onBasketPress' | 'onPriceCheckPress'> & {
  activeTab?: DashboardTab;
  devUI: TemporaryDevUIValues | null;
  onHomePress?: () => void;
}) {
  return (
    <View style={[styles.bottomNav, temporaryBoxStyle(devUI, 'bottomNav', { heightMode: 'height' })]}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ selected: activeTab === 'home' }}
        disabled={!onHomePress && activeTab !== 'home'}
        onPress={onHomePress}
        style={({ pressed }) => [
          styles.navItem,
          temporaryBoxStyle(devUI, 'bottomNavHomeItem'),
          pressed && styles.pressed,
        ]}
      >
        <DashboardIcon
          color={activeTab === 'home' ? COLORS.deepTeal : COLORS.muted}
          name="home-variant"
          size={temporaryIconSize(devUI, 'bottomNavHomeIcon', 25)}
          style={temporaryIconStyle(devUI, 'bottomNavHomeIcon')}
        />
        <Text style={[styles.navLabel, activeTab === 'home' && styles.navLabelActive, temporaryTextStyle(devUI, 'bottomNavHomeLabel')]}>Home</Text>
      </Pressable>
      <Pressable
        accessibilityLabel="Price Check"
        accessibilityRole="button"
        onPress={onPriceCheckPress}
        style={({ pressed }) => [
          styles.navItem,
          temporaryBoxStyle(devUI, 'bottomNavPriceCheckItem'),
          pressed && styles.pressed,
        ]}
      >
        <DashboardIcon
          color={COLORS.muted}
          name="magnify"
          size={temporaryIconSize(devUI, 'bottomNavPriceCheckIcon', 25)}
          style={temporaryIconStyle(devUI, 'bottomNavPriceCheckIcon')}
        />
        <Text numberOfLines={1} style={[styles.navLabel, temporaryTextStyle(devUI, 'bottomNavPriceCheckLabel')]}>Price Check</Text>
      </Pressable>
      <Pressable
        accessibilityLabel="My Basket"
        accessibilityRole="button"
        accessibilityState={{ disabled: !onBasketPress && activeTab !== 'basket', selected: activeTab === 'basket' }}
        disabled={!onBasketPress && activeTab !== 'basket'}
        onPress={onBasketPress}
        style={({ pressed }) => [
          styles.navItem,
          temporaryBoxStyle(devUI, 'bottomNavBasketItem'),
          pressed && styles.pressed,
        ]}
      >
        <DashboardIcon
          color={activeTab === 'basket' ? COLORS.deepTeal : COLORS.muted}
          name="basket-outline"
          size={temporaryIconSize(devUI, 'bottomNavBasketIcon', 25)}
          style={temporaryIconStyle(devUI, 'bottomNavBasketIcon')}
        />
        <Text style={[styles.navLabel, activeTab === 'basket' && styles.navLabelActive, temporaryTextStyle(devUI, 'bottomNavBasketLabel')]}>My Basket</Text>
      </Pressable>
    </View>
  );
}

export function HomeDashboardScreen({
  confirmedLocation = null,
  displayName = null,
  onBasketPress,
  onCreatePlanPress,
  onLocationPress,
  onPlanPress,
  onPriceCheckPress,
  onProfilePress,
  planDraft = null,
  recentChecks,
}: HomeDashboardScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const { width } = useWindowDimensions();
  const devUI = useTemporaryDevUIValues();
  const horizontalPadding = getDashboardHorizontalPadding(width);
  const greeting = getDashboardGreeting(new Date().getHours(), displayName);
  const mascotSize = width < 384 ? 72 : 84;
  const greetingWidth = Math.max(
    0,
    width - horizontalPadding * 2 - mascotSize + 8,
  );

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: temporaryNumber(devUI, 'screenPaddingTop', DASHBOARD_LAYOUT.contentTop),
            paddingRight: temporaryNumber(devUI, 'screenPaddingRight', horizontalPadding),
            paddingBottom: temporaryNumber(devUI, 'screenPaddingBottom', 24),
            paddingLeft: temporaryNumber(devUI, 'screenPaddingLeft', horizontalPadding),
          },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <DashboardHeader devUI={devUI} onProfilePress={onProfilePress} />
        <View style={styles.topSection}>
          <Text
            accessibilityRole="header"
            style={[
              styles.greeting,
              { maxWidth: greetingWidth },
              temporaryTextStyle(devUI, 'welcomeHeading'),
            ]}
          >
            {greeting}
          </Text>
          <Text
            style={[
              styles.supportingGreeting,
              { maxWidth: greetingWidth },
              temporaryTextStyle(devUI, 'welcomeSupporting'),
            ]}
          >
            Small choices. A brighter Malaysia.
          </Text>
          <Image
            accessible={false}
            resizeMode="contain"
            source={HOME_MASCOT_IMAGE}
            style={[styles.homeMascot, { height: mascotSize, width: mascotSize }]}
          />
          <DashboardLocationCard
            confirmedLocation={confirmedLocation}
            onLocationPress={onLocationPress}
          />
        </View>

        <Text accessibilityRole="header" style={styles.coreSectionTitle}>What would you like to do?</Text>
        <View style={[styles.actionsRow, temporaryBoxStyle(devUI, 'quickActionsRow'), { gap: temporaryNumber(devUI, 'quickActionsRowGap', 12) }]}>
          <QuickActionCard
            devUI={devUI}
            illustration={COMPARE_PRICES_IMAGE}
            onPress={onPriceCheckPress}
            supportingText="See where your items cost less"
            title="Compare prices"
            tone="orange"
          />
          <QuickActionCard
            devUI={devUI}
            disabled={!onPlanPress}
            illustration={PLAN_GROCERIES_IMAGE}
            onPress={onPlanPress}
            supportingText="Build your next grocery basket"
            title="Plan groceries"
            tone="green"
          />
        </View>

        <WeeklyPlanSection
          devUI={devUI}
          onBasketPress={onBasketPress}
          onCreatePlanPress={onCreatePlanPress}
          planDraft={planDraft}
        />
        <RecentlyCheckedSection
          devUI={devUI}
          horizontalPadding={horizontalPadding}
          recentChecks={recentChecks}
        />
        <ShoppingTipCard
          devUI={devUI}
          horizontalPadding={horizontalPadding}
          viewportWidth={width}
        />
      </ScrollView>
      <DashboardBottomNavigation activeTab="home" devUI={devUI} onBasketPress={onBasketPress} onPriceCheckPress={onPriceCheckPress} />
    </View>
  );
}

const COLORS = {
  background: '#FAF7F2',
  deepTeal: '#183F36',
  green: '#1E6B5C',
  greenBright: '#61B96C',
  muted: '#66766F',
  orange: '#F05C2B',
  orangeBright: '#FF7043',
  planSurface: '#EDF5E8',
  greenIconSurface: '#DCEBDD',
  softPeach: '#FCE9DD',
  softTeal: '#EAF5F4',
  surface: '#FFFFFF',
  tipSurface: '#F6F0E4',
  warning: '#B85C38',
  white: '#FFFFFF',
  yellow: '#F4B52B',
} as const;

const styles = StyleSheet.create({
  actionArrow: {
    alignItems: 'center',
    bottom: 15,
    height: 24,
    justifyContent: 'center',
    position: 'absolute',
    right: 15,
    width: 24,
  },
  actionCard: {
    borderRadius: 19,
    flex: 1,
    flexDirection: 'column',
    minHeight: 202,
    paddingHorizontal: 15,
    paddingTop: 12,
    position: 'relative',
  },
  actionCardGreen: {
    backgroundColor: '#EAF3E8',
  },
  actionCardOrange: {
    backgroundColor: COLORS.softPeach,
  },
  actionCopy: {
    flex: 1,
    marginTop: 7,
    minWidth: 0,
    paddingBottom: 25,
  },
  actionIllustrationWrap: {
    height: 96,
    justifyContent: 'center',
    width: '100%',
  },
  actionIllustration: {
    height: '100%',
    position: 'absolute',
    top: 0,
  },
  actionIllustrationCompare: {
    alignItems: 'flex-start',
  },
  actionIllustrationPlan: {
    alignItems: 'flex-start',
  },
  actionIllustrationCompareImage: {
    left: -3,
    maxWidth: 146,
    width: '100%',
  },
  actionIllustrationPlanImage: {
    left: -7,
    maxWidth: 146,
    width: '100%',
  },
  actionSupporting: {
    color: '#71817B',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 5,
  },
  actionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 17,
    lineHeight: 21,
  },
  actionsRow: {
    alignItems: 'stretch',
    flexDirection: 'row',
    gap: 12,
    marginTop: 12,
  },
  bottomNav: {
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderTopColor: 'rgba(24, 63, 54, 0.08)',
    borderTopWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-around',
    minHeight: 78,
    paddingBottom: 8,
    paddingHorizontal: 18,
    paddingTop: 8,
  },
  content: {
    paddingBottom: 24,
    paddingTop: DASHBOARD_LAYOUT.contentTop,
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  greeting: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: DASHBOARD_TYPE_SCALE.greeting,
    lineHeight: 29,
    marginTop: DASHBOARD_LAYOUT.greetingTop,
  },
  homeMascot: {
    position: 'absolute',
    right: 0,
    top: 2,
    zIndex: 1,
  },
  coreSectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: 19,
    lineHeight: 25,
    marginTop: 22,
  },
  locationCard: {
    alignItems: 'center',
    backgroundColor: COLORS.planSurface,
    borderRadius: 17,
    flexDirection: 'row',
    marginTop: 18,
    minHeight: 62,
    paddingHorizontal: 14,
    paddingVertical: 8,
    position: 'relative',
    zIndex: 2,
  },
  locationCardMain: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: 12,
    minWidth: 0,
  },
  locationCaption: {
    color: COLORS.green,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 14,
    lineHeight: 18,
  },
  locationChevron: {
    alignItems: 'center',
    flexShrink: 0,
    justifyContent: 'center',
    minHeight: DASHBOARD_LAYOUT.minimumTouchTarget,
    width: 32,
  },
  locationCopy: {
    flex: 1,
    minWidth: 0,
  },
  locationIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.greenIconSurface,
    borderRadius: 11,
    flexShrink: 0,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  locationValue: {
    color: COLORS.deepTeal,
    flexShrink: 1,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
    marginTop: 2,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 46,
  },
  logo: {
    height: 34,
    maxWidth: 154,
    width: 154,
  },
  navItem: {
    alignItems: 'center',
    borderRadius: 18,
    justifyContent: 'center',
    minHeight: 64,
    minWidth: 76,
    paddingHorizontal: 8,
  },
  navLabel: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 12,
    marginTop: 2,
  },
  navLabelActive: {
    color: COLORS.deepTeal,
  },
  activePlanPressable: {
    borderRadius: 18,
  },
  planStatusCard: {
    backgroundColor: COLORS.surface,
    borderColor: '#E3E9E4',
    borderRadius: 18,
    borderWidth: 1,
    padding: 16,
  },
  planStatusTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 16,
    lineHeight: 21,
  },
  planStatusDescription: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 4,
  },
  planStatusAction: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 5,
    marginTop: 10,
  },
  planStatusActionText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 14,
  },
  pressed: {
    opacity: 0.8,
  },
  profileButton: {
    alignItems: 'center',
    borderRadius: 99,
    justifyContent: 'center',
    minHeight: DASHBOARD_LAYOUT.minimumTouchTarget,
    minWidth: DASHBOARD_LAYOUT.minimumTouchTarget,
  },
  recentCard: {
    backgroundColor: '#F7F2EA',
    borderRadius: 18,
    minHeight: DASHBOARD_LAYOUT.recentMinHeight,
    overflow: 'hidden',
    paddingBottom: 11,
    paddingHorizontal: 10,
  },
  recentDistance: {
    color: COLORS.muted,
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 12,
    lineHeight: 17,
  },
  recentDistanceRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 2,
    marginTop: 2,
  },
  recentImage: {
    height: '100%',
    width: '100%',
  },
  recentImageWrap: {
    backgroundColor: '#FBF7F0',
    height: DASHBOARD_LAYOUT.recentImageHeight,
    marginHorizontal: -10,
    width: 'auto',
  },
  recentPrice: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.cardTitle,
    fontSize: DASHBOARD_TYPE_SCALE.body,
    lineHeight: 19,
    marginTop: 1,
  },
  recentProductName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.cardTitle,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 7,
  },
  recentRow: {
    gap: 10,
    paddingRight: 4,
  },
  recentStore: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: DASHBOARD_TYPE_SCALE.metadata,
    lineHeight: 16,
    marginTop: 1,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  section: {
    marginTop: DASHBOARD_LAYOUT.sectionGap,
  },
  sectionHeading: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: DASHBOARD_LAYOUT.sectionHeadingGap,
    minHeight: 30,
  },
  weeklySectionHeading: {
    marginBottom: 4,
  },
  sectionHeadingTitle: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  sectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: DASHBOARD_TYPE_SCALE.sectionTitle,
    lineHeight: 24,
  },
  supportingGreeting: {
    color: COLORS.green,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: DASHBOARD_TYPE_SCALE.supportingGreeting,
    lineHeight: 20,
    marginTop: 2,
  },
  topSection: {
    position: 'relative',
  },
  tipHeading: {
    marginBottom: DASHBOARD_LAYOUT.sectionHeadingGap,
    minHeight: 30,
  },
  tipBanner: {
    alignSelf: 'stretch',
    width: '100%',
  },
});
