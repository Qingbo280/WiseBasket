import { Ionicons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';
import { PriceCheckHeader } from '../components/price-check';
import { priceCheckLocationFontAssets, priceCheckLocationTokens } from '../components/price-check/priceCheckLocationTokens';
import { getLocationDisplayLabel, type ConfirmedLocation } from '../services/confirmedLocationContent';
import {
  searchLocationSuggestions,
  type LocationSuggestion,
} from '../services/locationSearch';

const TITLE_ACCENT_IMAGE = require('../../assets/images/price-check-reference/title-accent.png');
const CHEVRON_IMAGE = require('../../assets/images/price-check-reference/chevron-right.png');

export type ManualLocationSearchSuggestion = LocationSuggestion;

function getRecentLocationLabel(location: ConfirmedLocation): string {
  const label = getLocationDisplayLabel(location);
  if (label.trim().toLocaleLowerCase() === 'current location' && location.address.trim()) {
    return location.address;
  }
  return label;
}

interface ManualLocationSearchScreenProps {
  onBack: () => void;
  onSelectAddress?: (suggestion: ManualLocationSearchSuggestion) => void;
  onClearRecentLocations?: () => void;
  onUseCurrentLocation: () => void;
  recentLocations?: readonly ConfirmedLocation[];
  locationStatus?: 'idle' | 'loading' | 'error';
  locationMessage?: string;
}

const tokens = {
  colors: {
    actionBlue: '#0876C9',
    background: priceCheckLocationTokens.colors.background,
    clearButton: '#667579',
    deepTeal: priceCheckLocationTokens.colors.deepTeal,
    firstRow: '#FFF6EB',
    iconSurface: '#F3F5F3',
    inputSurface: '#FFFEFC',
    rowSurface: '#FFFFFF',
    secondaryText: priceCheckLocationTokens.colors.secondaryText,
    border: '#E5E9E6',
    orange: priceCheckLocationTokens.colors.orange,
  },
  fonts: priceCheckLocationTokens.fonts,
  spacing: {
    bodyHorizontal: 24,
    bodyHorizontalCompact: 20,
    bodyHorizontalNarrow: 22,
    bottomActionTop: 14,
    descriptionTop: 12,
    dividerTop: 20,
    headingTop: 18,
    rowGap: 8,
    searchTop: 16,
    sectionTop: 18,
    listTop: 10,
  },
} as const;

export function ManualLocationSearchScreen({
  onBack,
  onSelectAddress,
  onClearRecentLocations,
  onUseCurrentLocation,
  recentLocations = [],
  locationStatus = 'idle',
  locationMessage,
}: ManualLocationSearchScreenProps) {
  const { width } = useWindowDimensions();
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const horizontalPadding =
    width <= 360
      ? tokens.spacing.bodyHorizontalCompact
      : width <= 384
        ? tokens.spacing.bodyHorizontalNarrow
        : tokens.spacing.bodyHorizontal;
  const visibleRecentLocations = recentLocations.filter((location) => {
    const label = getLocationDisplayLabel(location).trim().toLocaleLowerCase();
    const address = location.address.trim().toLocaleLowerCase();
    return label !== 'current location' || (address && address !== 'current location');
  });

  useEffect(() => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 3) {
      setSuggestions([]);
      setSearching(false);
      setSearchError(null);
      return;
    }

    let active = true;
    setSearching(true);
    setSearchError(null);
    const timeout = setTimeout(() => {
      searchLocationSuggestions(trimmedQuery)
        .then((results) => {
          if (active) setSuggestions(results);
        })
        .catch((error: unknown) => {
          if (!active) return;
          setSuggestions([]);
          setSearchError(error instanceof Error ? error.message : 'Location search is unavailable.');
        })
        .finally(() => {
          if (active) setSearching(false);
        });
    }, 350);

    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [query]);

  if (!fontsLoaded) return <View style={styles.screen} />;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.screen}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <PriceCheckHeader compact={width <= 384} logoSize="small" onBack={onBack} />

        <View style={[styles.body, { paddingHorizontal: horizontalPadding }]}>
          <View style={styles.titleBlock}>
            <View style={styles.headingWrap}>
              <Text accessibilityRole="header" style={styles.heading}>Where should we{'\n'}compare prices?</Text>
              <Image accessibilityElementsHidden source={TITLE_ACCENT_IMAGE} style={styles.titleAccent} />
            </View>
            <Text style={styles.description}>
              We’ll show grocery prices from stores near this area.
            </Text>
          </View>

          <Pressable
            accessibilityLabel="Use my current location"
            accessibilityRole="button"
            accessibilityState={{ disabled: searching || locationStatus === 'loading' }}
            disabled={searching || locationStatus === 'loading'}
            onPress={onUseCurrentLocation}
            style={({ pressed }) => [styles.currentLocationCard, pressed && styles.pressed]}
          >
            <View style={styles.currentLocationIcon}>
              <Ionicons accessibilityElementsHidden color={tokens.colors.orange} name="locate" size={30} />
            </View>
            <View style={styles.currentLocationCopy}>
              <Text style={styles.currentLocationTitle}>{locationStatus === 'loading' ? 'Finding your location…' : 'Use my current location'}</Text>
              <Text style={styles.currentLocationSubtitle}>See prices near you</Text>
            </View>
            {locationStatus === 'loading' ? (
              <ActivityIndicator color={tokens.colors.orange} size="small" />
            ) : (
              <Ionicons accessibilityElementsHidden color={tokens.colors.deepTeal} name="chevron-forward" size={28} />
            )}
          </Pressable>
          {locationStatus === 'error' ? (
            <Text accessibilityLiveRegion="polite" style={styles.searchError}>
              {locationMessage ?? 'Unable to get your location. Please try again or search for an address.'}
            </Text>
          ) : null}

          <View style={styles.orDivider}>
            <View style={styles.orLine} />
            <Text style={styles.orText}>or</Text>
            <View style={styles.orLine} />
          </View>

          <View style={styles.searchField}>
            <Ionicons
              accessibilityElementsHidden
              color={tokens.colors.deepTeal}
              name="search-outline"
              size={24}
              style={styles.searchIcon}
            />
            <TextInput
              accessibilityLabel="Search for an address or area"
              autoCorrect={false}
              onChangeText={setQuery}
              placeholder="Search area or address"
              placeholderTextColor={tokens.colors.secondaryText}
              returnKeyType="search"
              selectionColor={tokens.colors.actionBlue}
              style={styles.searchInput}
              value={query}
            />
            {query.length > 0 ? (
              <Pressable
                accessibilityLabel="Clear address search"
                accessibilityRole="button"
                onPress={() => setQuery('')}
                style={({ pressed }) => [styles.clearButton, pressed && styles.pressed]}
              >
                <Ionicons accessibilityElementsHidden color={tokens.colors.inputSurface} name="close" size={22} />
              </Pressable>
            ) : null}
          </View>

          {query.trim().length >= 3 ? <Text style={[styles.sectionTitle, styles.searchResultsTitle]}>Search results</Text> : visibleRecentLocations.length > 0 ? (
            <View style={styles.recentHeadingRow}>
              <Text style={styles.sectionTitle}>Recent places</Text>
              <Pressable
                accessibilityRole="button"
                onPress={onClearRecentLocations}
                style={({ pressed }) => [styles.clearRecentButton, pressed && styles.pressed]}
              >
                <Text style={styles.clearRecentText}>Clear</Text>
              </Pressable>
            </View>
          ) : null}

          {searching ? (
            <View style={styles.searchStatus}>
              <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
              <Text style={styles.searchStatusText}>Searching locations...</Text>
            </View>
          ) : searchError ? (
            <Text accessibilityLiveRegion="polite" style={styles.searchError}>{searchError}</Text>
          ) : query.trim().length >= 3 && suggestions.length === 0 ? (
            <Text accessibilityLiveRegion="polite" style={styles.searchStatusText}>No locations found.</Text>
          ) : null}

          <View style={styles.suggestionList}>
            {query.trim().length < 3 && visibleRecentLocations.length > 0 ? (
              <View style={styles.recentContainer}>
                {visibleRecentLocations.map((location, index) => {
              const label = getRecentLocationLabel(location);
              return (
                <Pressable
                  accessibilityLabel={`Use recent location ${label}`}
                  accessibilityRole="button"
                  key={`${label}:${location.confirmedAt}`}
                  onPress={() => onSelectAddress?.({
                    id: `recent:${location.confirmedAt}`,
                    label,
                    address: location.address,
                    latitude: location.latitude ?? null,
                    longitude: location.longitude ?? null,
                    state: location.state,
                    district: location.district,
                  })}
                  style={({ pressed }) => [
                    styles.suggestionRow,
                    index < visibleRecentLocations.length - 1 && styles.suggestionRowDivider,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.locationIconBubble}>
                    <Ionicons accessibilityElementsHidden color={tokens.colors.secondaryText} name="location" size={27} />
                  </View>
                  <View style={styles.suggestionCopy}>
                    <Text numberOfLines={1} ellipsizeMode="tail" style={styles.suggestionTitle}>{label}</Text>
                    {location.address !== label ? (
                      <Text numberOfLines={2} ellipsizeMode="tail" style={styles.suggestionAddress}>
                        {location.address}
                      </Text>
                    ) : null}
                  </View>
                  <Ionicons accessibilityElementsHidden color={tokens.colors.secondaryText} name="chevron-forward" size={25} />
                </Pressable>
              );
                })}
              </View>
            ) : null}
            {query.trim().length >= 3 && suggestions.length > 0 ? (
              <View style={styles.recentContainer}>
                {suggestions.map((suggestion, index) => (
              <Pressable
                accessibilityLabel={`${suggestion.label}, ${suggestion.address}`}
                accessibilityRole={onSelectAddress ? 'button' : undefined}
                key={suggestion.id}
                onPress={onSelectAddress ? () => onSelectAddress(suggestion) : undefined}
                style={({ pressed }) => [
                  styles.suggestionRow,
                  index < suggestions.length - 1 && styles.suggestionRowDivider,
                  pressed && styles.pressed,
                ]}
              >
                <View style={styles.locationIconBubble}>
                  <Ionicons
                    accessibilityElementsHidden
                    color={tokens.colors.orange}
                    name="location-sharp"
                    size={31}
                  />
                </View>
                <View style={styles.suggestionCopy}>
                <Text numberOfLines={1} ellipsizeMode="tail" style={styles.suggestionTitle}>{suggestion.label}</Text>
                  <Text style={styles.suggestionAddress}>{suggestion.address}</Text>
                </View>
                <Image
                  accessibilityElementsHidden
                  source={CHEVRON_IMAGE}
                  style={styles.chevron}
                />
              </Pressable>
                ))}
              </View>
            ) : null}
          </View>

        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  body: {
    minWidth: 0,
    flexGrow: 0,
    flexShrink: 0,
    paddingBottom: 28,
    paddingTop: 8,
  },
  chevron: {
    height: 24,
    marginLeft: 6,
    resizeMode: 'contain',
    width: 24,
  },
  clearButton: {
    alignItems: 'center',
    backgroundColor: tokens.colors.clearButton,
    borderRadius: 20,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  clearRecentButton: {
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
    minHeight: 48,
    paddingHorizontal: 10,
  },
  clearRecentText: {
    color: tokens.colors.orange,
    fontFamily: tokens.fonts.bodySemibold,
    fontSize: 15,
  },
  titleBlock: {
    marginTop: 14,
  },
  currentLocationCard: {
    alignItems: 'center',
    backgroundColor: tokens.colors.firstRow,
    borderRadius: 18,
    flexDirection: 'row',
    gap: 14,
    marginTop: 28,
    minHeight: 76,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  currentLocationCopy: {
    flex: 1,
    minWidth: 0,
  },
  currentLocationIcon: {
    alignItems: 'center',
    backgroundColor: '#FFE8D7',
    borderRadius: 12,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  currentLocationSubtitle: {
    color: tokens.colors.secondaryText,
    fontFamily: tokens.fonts.body,
    fontSize: 16,
    lineHeight: 21,
    marginTop: 1,
  },
  currentLocationTitle: {
    color: tokens.colors.deepTeal,
    fontFamily: tokens.fonts.bodySemibold,
    fontSize: 17,
    lineHeight: 23,
  },
  description: {
    color: tokens.colors.secondaryText,
    fontFamily: tokens.fonts.body,
    fontSize: 16,
    lineHeight: 23,
    marginTop: 14,
  },
  orDivider: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    marginTop: 15,
  },
  orLine: {
    backgroundColor: tokens.colors.border,
    flex: 1,
    height: 1,
  },
  orText: {
    color: tokens.colors.secondaryText,
    fontFamily: tokens.fonts.body,
    fontSize: 14,
  },
  heading: {
    color: tokens.colors.deepTeal,
    fontFamily: tokens.fonts.heading,
    fontSize: 31,
    lineHeight: 36,
    paddingRight: 4,
  },
  headingWrap: {
    paddingRight: 32,
    position: 'relative',
  },
  recentHeadingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
  },
  locationIconBubble: {
    alignItems: 'center',
    backgroundColor: tokens.colors.iconSurface,
    borderRadius: 11,
    flexShrink: 0,
    height: 38,
    justifyContent: 'center',
    width: 38,
  },
  pressed: {
    opacity: 0.78,
  },
  screen: {
    backgroundColor: tokens.colors.background,
    flex: 1,
  },
  searchField: {
    alignItems: 'center',
    backgroundColor: tokens.colors.inputSurface,
    borderColor: tokens.colors.border,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    height: 56,
    marginTop: 18,
    paddingHorizontal: 12,
  },
  searchIcon: {
    marginHorizontal: 5,
  },
  searchError: {
    color: '#A33A2B',
    fontFamily: tokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 12,
  },
  searchStatus: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  searchStatusText: {
    color: tokens.colors.secondaryText,
    fontFamily: tokens.fonts.body,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 12,
  },
  searchInput: {
    color: tokens.colors.deepTeal,
    flex: 1,
    fontFamily: tokens.fonts.body,
    fontSize: 16,
    lineHeight: 22,
    minWidth: 0,
    ...(Platform.OS === 'web' ? { outlineWidth: 0 } : {}),
    paddingHorizontal: 9,
    paddingVertical: 0,
  },
  scrollContent: {
    paddingBottom: 0,
  },
  sectionTitle: {
    color: tokens.colors.deepTeal,
    fontFamily: tokens.fonts.bodySemibold,
    fontSize: 19,
    lineHeight: 25,
  },
  searchResultsTitle: {
    marginTop: 26,
  },
  suggestionAddress: {
    color: tokens.colors.secondaryText,
    fontFamily: tokens.fonts.body,
    fontSize: 14,
    lineHeight: 19,
    marginTop: 3,
  },
  suggestionCopy: {
    flex: 1,
    marginLeft: 12,
    minWidth: 0,
  },
  suggestionList: {
    marginTop: 0,
  },
  recentContainer: {
    backgroundColor: tokens.colors.rowSurface,
    borderColor: tokens.colors.border,
    borderRadius: 20,
    borderWidth: 1,
    overflow: 'hidden',
  },
  suggestionRow: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 76,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  suggestionRowDivider: {
    borderBottomColor: tokens.colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  suggestionTitle: {
    color: tokens.colors.deepTeal,
    fontFamily: tokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  titleAccent: {
    height: 52,
    position: 'absolute',
    right: 6,
    resizeMode: 'contain',
    top: -2,
    width: 29,
  },
});
