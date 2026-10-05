import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { priceCheckLocationTokens } from './priceCheckLocationTokens';

type IoniconName = ComponentProps<typeof Ionicons>['name'];
type NextStepOptionVariant = 'primary' | 'secondary' | 'tertiary';

export interface NextStepOptionCardProps {
  icon: IoniconName;
  onPress: () => void;
  supportingText: string;
  title: string;
  visualVariant: NextStepOptionVariant;
}

export function NextStepOptionCard({
  icon,
  onPress,
  supportingText,
  title,
  visualVariant,
}: NextStepOptionCardProps) {
  const isPrimary = visualVariant === 'primary';

  return (
    <Pressable
      accessibilityLabel={`${title}. ${supportingText}`}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        styles[visualVariant],
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.iconColumn}>
        <Ionicons
          accessibilityElementsHidden
          color={isPrimary ? '#FFFFFF' : priceCheckLocationTokens.colors.deepTeal}
          name={icon}
          size={34}
        />
      </View>
      <View style={[styles.divider, isPrimary ? styles.primaryDivider : styles.softDivider]} />
      <View style={styles.copy}>
        <Text style={[styles.title, isPrimary ? styles.primaryTitle : styles.darkTitle]}>
          {title}
        </Text>
        <Text style={[styles.supportingText, isPrimary ? styles.primarySupportingText : styles.softSupportingText]}>
          {supportingText}
        </Text>
      </View>
      <Ionicons
        accessibilityElementsHidden
        color={isPrimary ? '#FFFFFF' : priceCheckLocationTokens.colors.deepTeal}
        name="chevron-forward"
        size={30}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    alignItems: 'center',
    borderRadius: 30,
    flexDirection: 'row',
    minHeight: 88,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  copy: {
    flex: 1,
    minWidth: 0,
    paddingHorizontal: 12,
  },
  darkTitle: {
    color: priceCheckLocationTokens.colors.deepTeal,
  },
  divider: {
    height: 56,
    width: 2,
  },
  iconColumn: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 56,
    width: 52,
  },
  primary: {
    backgroundColor: priceCheckLocationTokens.colors.green,
  },
  primaryDivider: {
    backgroundColor: 'rgba(255,255,255,0.45)',
  },
  primarySupportingText: {
    color: '#D9F0E1',
  },
  primaryTitle: {
    color: '#FFFFFF',
  },
  pressed: {
    opacity: 0.78,
  },
  secondary: {
    backgroundColor: '#FFFEFC',
    borderColor: priceCheckLocationTokens.colors.green,
    borderWidth: 2,
  },
  softDivider: {
    backgroundColor: '#CFE3D4',
  },
  softSupportingText: {
    color: priceCheckLocationTokens.colors.secondaryText,
  },
  tertiary: {
    backgroundColor: '#F2F0E9',
  },
  title: {
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 18,
    lineHeight: 23,
  },
  supportingText: {
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 1,
  },
});
