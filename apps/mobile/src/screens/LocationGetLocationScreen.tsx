import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import {
  LocationChoiceCard,
  PriceCheckHeader,
  PriceCheckHeading,
} from '../components/price-check';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import {
  getLocationDisplayLabel,
  type LocationCandidate,
} from '../services/confirmedLocationContent';

const HERO_IMAGE = require('../../assets/images/price-check-reference/location-hero-revised.png');
const CURRENT_LOCATION_IMAGE = require('../../assets/images/price-check-reference/current-location.png');
const ENTER_ADDRESS_IMAGE = require('../../assets/images/price-check-reference/enter-address.png');

type LocationGetLocationScreenProps = {
  onEnterAddress: () => void;
  onUseCurrentLocation?: () => void;
  onBack?: () => void;
  onChangeLocation?: () => void;
  onConfirmLocation?: () => void;
  pendingLocation?: LocationCandidate | null;
  locationStatus?: 'idle' | 'loading' | 'error';
  locationMessage?: string;
};

/**
 * The shared first location step for the Price Check and Plan test flows.
 *
 * This is intentionally provider-free: it keeps deprecated planning and food
 * catalog routes out of the test bundle while preserving the approved
 * location-page presentation.
 */
export function LocationGetLocationScreen({
  onBack,
  onChangeLocation,
  onConfirmLocation,
  onEnterAddress,
  pendingLocation,
  onUseCurrentLocation,
  locationStatus = 'idle',
  locationMessage,
}: LocationGetLocationScreenProps) {
  const { height, width } = useWindowDimensions();
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const compact = width <= 384 && height <= 820;
  const pageHorizontalPadding = width <= 360 ? 20 : width <= 384 ? 22 : 24;

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  if (pendingLocation) {
    const locationLabel = getLocationDisplayLabel(pendingLocation);
    const confirming = locationStatus === 'loading';

    return (
      <View style={styles.wrapper}>
        <ScrollView
          contentContainerStyle={[styles.content, compact && styles.compactContent]}
          showsVerticalScrollIndicator={false}
        >
          <PriceCheckHeader onBack={onBack} />
          <View
            style={[
              styles.confirmationContent,
              compact && styles.compactConfirmationContent,
              { paddingHorizontal: pageHorizontalPadding },
            ]}
          >
            <Text style={styles.confirmationHeading}>Confirm your location</Text>
            <Text style={styles.confirmationDescription}>
              WiseBasket will use this shopping location for nearby prices and planning.
            </Text>

            <View style={styles.confirmationCard}>
              <View style={styles.confirmationIcon}>
                <Ionicons
                  accessibilityElementsHidden
                  color="#FFFFFF"
                  name="location-sharp"
                  size={29}
                />
              </View>
              <View style={styles.confirmationCopy}>
                <Text style={styles.confirmationEyebrow}>
                  {pendingLocation.source === 'gps' ? 'Detected location' : 'Selected location'}
                </Text>
                <Text style={styles.confirmationAddress}>{locationLabel}</Text>
                {pendingLocation.address !== locationLabel ? (
                  <Text style={styles.confirmationAddressDetail}>{pendingLocation.address}</Text>
                ) : null}
              </View>
            </View>

            <Pressable
              accessibilityLabel="Confirm this location"
              accessibilityRole="button"
              accessibilityState={{ disabled: confirming || !onConfirmLocation }}
              disabled={confirming || !onConfirmLocation}
              onPress={onConfirmLocation}
              style={({ pressed }) => [
                styles.confirmButton,
                (confirming || !onConfirmLocation) && styles.disabledButton,
                pressed && styles.pressed,
              ]}
            >
              {confirming ? <ActivityIndicator color="#FFFFFF" size="small" /> : null}
              <Text style={styles.confirmButtonText}>{confirming ? 'Saving…' : 'Confirm this location'}</Text>
            </Pressable>
            <Pressable
              accessibilityLabel="Change location"
              accessibilityRole="button"
              disabled={!onChangeLocation}
              onPress={onChangeLocation}
              style={({ pressed }) => [styles.changeButton, pressed && styles.pressed]}
            >
              <Text style={styles.changeButtonText}>Change location</Text>
            </Pressable>

            {locationStatus === 'error' ? (
              <Text accessibilityLiveRegion="polite" style={styles.locationStatusText}>
                {locationMessage ?? 'Your location could not be saved. Please try again.'}
              </Text>
            ) : null}
          </View>
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.wrapper}>
      <ScrollView
        contentContainerStyle={[styles.content, compact && styles.compactContent]}
        showsVerticalScrollIndicator={false}
      >
        <PriceCheckHeader onBack={onBack} />
        <View
          style={[
            styles.pageContent,
            compact && styles.compactPageContent,
            { paddingHorizontal: pageHorizontalPadding },
          ]}
        >
          <PriceCheckHeading compact={compact} />
          <View
            style={[
              styles.heroWrap,
              compact && styles.compactHeroWrap,
              { marginHorizontal: -pageHorizontalPadding },
            ]}
          >
            <Image accessibilityElementsHidden source={HERO_IMAGE} style={styles.heroImage} />
            {width >= 384 ? (
              <View pointerEvents="none" style={styles.heroBubbleCopy}>
                <Text style={styles.heroBubbleText}>Same items.{`\n`}Better prices.{`\n`}Near you.</Text>
              </View>
            ) : null}
          </View>
          <View
            style={[
              styles.choiceList,
              compact && styles.compactChoiceList,
              { marginHorizontal: -(pageHorizontalPadding >= 24 ? 8 : 4) },
            ]}
          >
            <LocationChoiceCard
              accessibilityLabel="Use current location"
              compact={compact}
              imageSource={CURRENT_LOCATION_IMAGE}
              onPress={onUseCurrentLocation ?? (() => undefined)}
              subtitle="See prices near you"
              title="Use current location"
            />
            <LocationChoiceCard
              accessibilityLabel="Enter an address"
              compact={compact}
              imageSource={ENTER_ADDRESS_IMAGE}
              onPress={onEnterAddress}
              subtitle="See prices near an address"
              title="Enter an address"
            />
            {locationStatus !== 'idle' ? (
              <View accessibilityLiveRegion="polite" style={styles.locationStatus}>
                {locationStatus === 'loading' ? (
                  <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
                ) : null}
                <Text style={styles.locationStatusText}>
                  {locationMessage ?? (locationStatus === 'loading' ? 'Getting your locationâ€¦' : 'Unable to get your location.')}
                </Text>
              </View>
            ) : null}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  changeButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: priceCheckLocationTokens.iconSizes.touchTarget,
    marginTop: 8,
    paddingHorizontal: 12,
  },
  changeButtonText: {
    color: priceCheckLocationTokens.colors.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
    lineHeight: 22,
  },
  choiceList: {
    gap: priceCheckLocationTokens.spacing.cardGap,
    marginTop: priceCheckLocationTokens.spacing.cardsTop,
  },
  compactChoiceList: {
    gap: 10,
    marginTop: 2,
  },
  compactContent: {
    paddingBottom: 12,
  },
  compactConfirmationContent: {
    paddingTop: 20,
  },
  content: {
    paddingBottom: 24,
  },
  confirmationAddress: {
    color: priceCheckLocationTokens.colors.deepTeal,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 27,
    marginTop: 3,
  },
  confirmationAddressDetail: {
    color: priceCheckLocationTokens.colors.secondaryText,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 4,
  },
  confirmationCard: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderRadius: priceCheckLocationTokens.radius.card,
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
    minHeight: 100,
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  confirmationContent: {
    paddingBottom: 24,
    paddingTop: priceCheckLocationTokens.spacing.headingTop,
  },
  confirmationCopy: {
    flex: 1,
    minWidth: 0,
  },
  confirmationDescription: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 18,
    lineHeight: 25,
    marginTop: 12,
  },
  confirmationEyebrow: {
    color: priceCheckLocationTokens.colors.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  confirmationHeading: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 38,
    lineHeight: 43,
    paddingRight: 18,
  },
  confirmationIcon: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 99,
    flexShrink: 0,
    height: 52,
    justifyContent: 'center',
    width: 52,
  },
  confirmButton: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 18,
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    marginTop: 24,
    minHeight: 54,
    paddingHorizontal: 16,
  },
  confirmButtonText: {
    color: '#FFFFFF',
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 17,
    lineHeight: 23,
  },
  disabledButton: {
    opacity: 0.7,
  },
  fontLoading: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  heroImage: {
    height: '100%',
    resizeMode: 'cover',
    width: '100%',
  },
  heroBubbleCopy: {
    alignItems: 'center',
    justifyContent: 'center',
    position: 'absolute',
    right: 24,
    top: 18,
    transform: [{ rotate: '-5deg' }],
    width: 120,
  },
  heroBubbleText: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 13,
    lineHeight: 15,
    textAlign: 'center',
  },
  heroWrap: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    height: priceCheckLocationTokens.spacing.heroHeight,
    marginTop: priceCheckLocationTokens.spacing.heroTop,
    overflow: 'hidden',
    width: 'auto',
  },
  compactHeroWrap: {
    height: 220,
    marginTop: 2,
  },
  pageContent: {
    paddingTop: priceCheckLocationTokens.spacing.headingTop,
  },
  locationStatus: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    paddingHorizontal: 8,
  },
  locationStatusText: {
    color: priceCheckLocationTokens.colors.secondaryText,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.78,
  },
  compactPageContent: {
    paddingTop: 18,
  },
  wrapper: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
});
